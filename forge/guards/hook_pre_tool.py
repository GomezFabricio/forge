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


def _is_guard_disabled() -> bool:
    """Return True if FORGE_GUARD_DISABLE is set to a truthy value (non-empty, not "0")."""
    val = os.environ.get("FORGE_GUARD_DISABLE", "")
    return bool(val) and val != "0"


def _hash_command(command: str) -> str:
    """Return the first 16 hex characters of the SHA-256 digest of command."""
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
    """Append a decision or error event to the guard JSONL log.

    Swallows all errors (fail-open: logging must never block the hook).
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
        pass  # Fail-open: never let logging block the hook


def _log_error(
    *,
    message: str,
    log_path: Path,
) -> None:
    """Append an error event to the guard JSONL log (fail-open)."""
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
        pass  # Fail-open: never let logging block the hook


def _evaluate_rules(command: str, rules: list, command_hash: str, log_path: Path) -> dict:
    """Evaluate guardrails rules in order; return first-match decision or {}.

    :param command: The Bash command string from the hook payload.
    :param rules: List of rule dicts from guardrails.yaml.
    :param command_hash: SHA-256[:16] of command for logging.
    :param log_path: Path to the guard JSONL log.
    :returns: Decision dict (deny/ask JSON) or {} if no rule matched.
    """
    for rule in rules:
        # Validate required fields — skip invalid rules (fail-open, log error once)
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

        # Compile regex — per-rule ignorecase flag
        flags = re.IGNORECASE if rule.get("ignorecase") else 0
        try:
            regex = re.compile(pattern_str, flags)
        except re.error as exc:
            _log_error(
                message=f"invalid regex pattern '{pattern_str}': {exc}",
                log_path=log_path,
            )
            continue

        if not regex.search(command):
            continue

        # Match found — build decision
        permission = "deny" if action == "block" else "ask"

        # Build reason string
        alternative = rule.get("alternative", "")
        if alternative:
            decision_reason = f"Razón: {reason} — Alternativa: {alternative}"
        else:
            decision_reason = f"Razón: {reason}"

        # Log the decision
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


def process_hook(input_data: dict, *, log_path: Path | None = None) -> dict:
    """Process a Claude Code PreToolUse hook payload.

    :param input_data: Parsed JSON from stdin.
    :param log_path: Override log file path (for tests).
    :returns: Decision dict or {} (no decision = normal permission flow).
    """
    # Kill-switch: FORGE_GUARD_DISABLE
    if _is_guard_disabled():
        return {}

    # Only act on Bash tool with a non-empty command
    if input_data.get("tool_name") != "Bash":
        return {}

    tool_input = input_data.get("tool_input")
    if not isinstance(tool_input, dict):
        return {}

    command = tool_input.get("command", "")
    if not isinstance(command, str) or not command.strip():
        return {}

    # Resolve cwd from payload (NOT os.getcwd())
    cwd_str = input_data.get("cwd", "")
    if not cwd_str:
        return {}

    cwd = Path(cwd_str)
    guardrails_path = cwd / "docs" / "auditoria" / "guardrails.yaml"

    # No guardrails file -> unaffected project, pass through
    if not guardrails_path.exists():
        return {}

    # Resolve log path
    if log_path is None:
        log_path = cwd / ".forge" / "auditoria-guard.jsonl"

    # Parse guardrails file
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


def main() -> int:
    """Entry point for Claude Code PreToolUse hook.

    Reads JSON from stdin, calls process_hook, writes JSON to stdout.
    Always exits 0 (fail-open per ADR-4).
    """
    try:
        raw = sys.stdin.buffer.read().decode("utf-8")
        input_data = json.loads(raw)
    except Exception:  # noqa: BLE001
        sys.stdout.write("{}")
        return 0  # Fail-open: exit 0 even on parse error

    try:
        result = process_hook(input_data)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[fg-guard] error: {type(exc).__name__}\n")
        result = {}

    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
