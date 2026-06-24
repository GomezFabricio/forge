"""Hook PreToolUse del guardrail de operaciones destructivas.

Intercepta comandos Bash antes de ejecución y evalúa reglas de la configuración
del proyecto (docs/auditoria/guardrails.yaml). Primera regla que hace match gana.

Acciones:
  block   -> permissionDecision "deny"  (bloqueado, no se ejecuta)
  confirm -> permissionDecision "ask"   (Claude Code pide confirmación al usuario)

Fail-open (ADR-4): cualquier error interno -> `{}` y exit 0. El dev loop nunca se bloquea
por un bug en el hook. El hook NO opera si:
  - payload no es JSON válido
  - tool_name != "Bash" o command vacío
  - docs/auditoria/guardrails.yaml no existe en el cwd del payload
  - FORGE_GUARD_DISABLE está seteado (no vacío, no "0")

Log: .forge/auditoria-guard.jsonl bajo el cwd del payload.
  - Solo se loguean decisiones (deny/ask) y errores.
  - No se guarda el command completo — solo SHA-256[:16] para correlación.
  - Se loguea el pattern de la regla que hizo match y la acción.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Mitigación de ReDoS (Tarea B / ADR-4, defensa en profundidad).
#
# Un guardrails.yaml escrito por el usuario puede contener un patrón vulnerable a
# backtracking catastrófico (ej. ``(a+)+$``). El costo de ese backtracking escala
# con la longitud del INPUT, no del patrón: un comando más largo puede convertir un
# match lento en uno que gira por decenas de segundos, frenando el dev loop. Eso es
# peor que una excepción (que falla-abierto al instante) porque un proceso colgado
# mantiene a Claude Code esperando — anulando la intención del ADR-4 de nunca
# bloquear el loop.
#
# Acotamos el string del comando que se le pasa a cada regex a MAX_COMMAND_LEN
# caracteres. Truncar el input topea el costo de backtracking del peor caso a un
# techo fijo sin importar el patrón, tanto en Windows como en Unix, sin threads ni
# señales extra. Se evaluó y descartó un timeout real por evaluación: un join basado
# en ``threading`` no puede interrumpir un ``re.search`` CPU-bound bajo CPython
# porque el motor de regex mantiene el GIL mientras matchea (medido: un join de 2s
# recién retornó tras ~23s), así que daría falsa seguridad. El cap de longitud es
# entonces la mitigación principal, y la única confiable, acá.
#
# Riesgo residual (aceptado, documentado): un patrón patológico cuyo umbral de
# explosión esté POR DEBAJO de MAX_COMMAND_LEN puede seguir siendo lento con un
# comando corto. El guard es best-effort; un patrón catastrófico escrito por el
# usuario sigue siendo responsabilidad del usuario (ver README "Defensa en
# profundidad" / guia-de-uso §6).
# 8192 chars cubren cómodamente one-liners de Bash realistas manteniendo el costo de
# backtracking del input truncado despreciable (medido sub-milisegundo).
MAX_COMMAND_LEN = 8192


def _is_guard_disabled() -> bool:
    """Devuelve True si FORGE_GUARD_DISABLE tiene un valor truthy (no vacío, distinto de "0")."""
    val = os.environ.get("FORGE_GUARD_DISABLE", "")
    return bool(val) and val != "0"


def _hash_command(command: str) -> str:
    """Devuelve los primeros 16 caracteres hex del digest SHA-256 de command."""
    digest = hashlib.sha256(command.encode("utf-8")).hexdigest()
    return digest[:16]


def _log_decision(
    *,
    action: str,
    pattern: str,
    command_hash: str,
    reason: str,
    log_path: Path,
) -> None:
    """Agrega un evento de decisión o error al log JSONL del guard.

    Traga todos los errores (fail-open: el logging nunca debe bloquear el hook).
    """
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
        entry = {
            "ts": ts,
            "action": action,
            "pattern": pattern,
            "command_hash": command_hash,
            "reason": reason,
        }
        with open(log_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:  # noqa: BLE001
        pass  # Fail-open: nunca dejar que el logging bloquee el hook


def _log_error(
    *,
    message: str,
    log_path: Path,
) -> None:
    """Agrega un evento de error al log JSONL del guard (fail-open)."""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
        entry = {
            "ts": ts,
            "action": "error",
            "message": message,
        }
        with open(log_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:  # noqa: BLE001
        pass  # Fail-open: nunca dejar que el logging bloquee el hook


def _evaluate_rules(command: str, rules: list, command_hash: str, log_path: Path) -> dict:
    """Evalúa las reglas de guardrails en orden; devuelve la decisión de la primera que matchea o {}.

    :param command: El string del comando Bash del payload del hook.
    :param rules: Lista de dicts de regla de guardrails.yaml.
    :param command_hash: SHA-256[:16] del comando para el log.
    :param log_path: Path al log JSONL del guard.
    :returns: Dict de decisión (JSON deny/ask) o {} si ninguna regla matcheó.
    """
    # Mitigación de ReDoS: acotar el input que se le pasa a cada regex (ver MAX_COMMAND_LEN).
    # El hash usado para el log de auditoría se calcula sobre el comando COMPLETO aguas arriba,
    # así que la correlación no se ve afectada; solo se topea el texto que se matchea.
    match_target = command[:MAX_COMMAND_LEN]

    for rule in rules:
        # Validar campos requeridos — saltear reglas inválidas (fail-open, loguear el error una vez)
        pattern_str = rule.get("pattern")
        action = rule.get("action")
        reason = rule.get("reason")

        if not isinstance(pattern_str, str) or not pattern_str or not action or not reason:
            _log_error(
                message=f"invalid rule skipped (missing pattern/action/reason): {rule}",
                log_path=log_path,
            )
            continue

        if action not in ("block", "confirm"):
            _log_error(
                message=f"invalid rule action '{action}' skipped",
                log_path=log_path,
            )
            continue

        # Compilar la regex — flag ignorecase por regla
        flags = re.IGNORECASE if rule.get("ignorecase") else 0
        try:
            regex = re.compile(pattern_str, flags)
        except re.error as exc:
            _log_error(
                message=f"invalid regex pattern '{pattern_str}': {exc}",
                log_path=log_path,
            )
            continue

        if not regex.search(match_target):
            continue

        # Match encontrado — construir la decisión
        permission = "deny" if action == "block" else "ask"

        # Construir el string de la razón
        alternative = rule.get("alternative", "")
        if alternative:
            decision_reason = f"Razón: {reason} — Alternativa: {alternative}"
        else:
            decision_reason = f"Razón: {reason}"

        # Loguear la decisión
        _log_decision(
            action=action,
            pattern=pattern_str,
            command_hash=command_hash,
            reason=decision_reason,
            log_path=log_path,
        )

        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": permission,
                "permissionDecisionReason": decision_reason,
            }
        }

    return {}


def _resolve_log_path(input_data: dict, log_path: Path | None) -> Path | None:
    """Path best-effort del log del guard para los paths de auditoría de error (fail-open).

    Devuelve el override explícito si se da; si no, lo deriva del cwd del payload.
    Devuelve None cuando no se puede determinar una ubicación, en cuyo caso el
    llamador saltea la auditoría en silencio (nunca lanza). Traga todos los errores.
    """
    if log_path is not None:
        return log_path
    try:
        cwd_str = input_data.get("cwd", "") if isinstance(input_data, dict) else ""
        if not cwd_str:
            return None
        return Path(cwd_str) / ".forge" / "auditoria-guard.jsonl"
    except Exception:  # noqa: BLE001
        return None


def _process_hook_inner(input_data: dict, *, log_path: Path | None = None) -> dict:
    """Lógica central del hook. Puede lanzar — la envuelve el guard fail-open de process_hook."""
    # Kill-switch: FORGE_GUARD_DISABLE
    if _is_guard_disabled():
        return {}

    # Solo actuar sobre la tool Bash con un comando no vacío
    if input_data.get("tool_name") != "Bash":
        return {}

    tool_input = input_data.get("tool_input")
    if not isinstance(tool_input, dict):
        return {}

    command = tool_input.get("command", "")
    if not isinstance(command, str) or not command.strip():
        return {}

    # Resolver el cwd desde el payload (NO os.getcwd())
    cwd_str = input_data.get("cwd", "")
    if not cwd_str:
        return {}

    cwd = Path(cwd_str)
    guardrails_path = cwd / "docs" / "auditoria" / "guardrails.yaml"

    # Sin archivo de guardrails -> proyecto no afectado, pasar de largo
    if not guardrails_path.exists():
        return {}

    # Resolver el path del log
    if log_path is None:
        log_path = cwd / ".forge" / "auditoria-guard.jsonl"

    # Parsear el archivo de guardrails
    try:
        import yaml  # noqa: PLC0415
        guardrails = yaml.safe_load(guardrails_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _log_error(message=f"guardrails.yaml parse error: {type(exc).__name__}: {exc}", log_path=log_path)
        return {}

    if not isinstance(guardrails, dict):
        _log_error(message="guardrails.yaml: root is not a mapping", log_path=log_path)
        return {}

    rules = guardrails.get("rules", [])
    if not isinstance(rules, list):
        return {}

    command_hash = _hash_command(command)
    return _evaluate_rules(command, rules, command_hash, log_path)


def process_hook(input_data: dict, *, log_path: Path | None = None) -> dict:
    """Procesa un payload del hook PreToolUse de Claude Code.

    Guard fail-open (ADR-4): cualquier excepción inesperada se traga y devuelve {}.
    A diferencia de un swallow pelado, un fallo inesperado acá TAMBIÉN deja una traza
    de auditoría legible por máquina (``action="error"``) para que las excepciones que
    se escapan no sean invisibles. La línea de auditoría lleva solo el NOMBRE del TIPO
    de excepción como marcador estable — nunca el comando crudo — preservando el
    contrato de privacidad.

    :param input_data: JSON parseado de stdin.
    :param log_path: Override del path del log (para tests).
    :returns: Dict de decisión o {} (sin decisión = flujo normal de permisos).
    """
    try:
        return _process_hook_inner(input_data, log_path=log_path)
    except Exception as exc:  # noqa: BLE001
        # D3: emitir un registro de auditoría legible por máquina en el camino de error.
        # Usar solo el nombre del tipo de excepción como marcador estable — NO incluir el
        # comando crudo ni los args de la excepción (que podrían reflejar el input).
        audit_path = _resolve_log_path(input_data, log_path)
        if audit_path is not None:
            _log_error(
                message=f"unexpected error in process_hook: {type(exc).__name__}",
                log_path=audit_path,
            )
        return {}  # Fail-open: nunca re-lanzar, nunca salir con código distinto de cero


def main() -> int:
    """Entry point del hook PreToolUse de Claude Code.

    Lee JSON de stdin, llama a process_hook, escribe JSON a stdout.
    Siempre sale con 0 (fail-open según ADR-4).
    """
    try:
        raw = sys.stdin.buffer.read().decode("utf-8")
        input_data = json.loads(raw)
    except Exception:  # noqa: BLE001
        sys.stdout.write("{}")
        return 0  # Fail-open: exit 0 incluso ante error de parseo

    try:
        result = process_hook(input_data)
    except Exception as exc:  # noqa: BLE001
        # Backstop: process_hook tiene su propia auditoría fail-open, pero si alguna vez
        # lanza antes de que ese guard corra, igual dejar una traza legible por máquina
        # acá (action="error", solo el nombre del tipo — nunca el comando crudo).
        sys.stderr.write(f"[fg-guard] error: {type(exc).__name__}\n")
        audit_path = _resolve_log_path(input_data, None)
        if audit_path is not None:
            _log_error(
                message=f"unexpected error in main: {type(exc).__name__}",
                log_path=audit_path,
            )
        result = {}

    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
