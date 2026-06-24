"""Hook UserPromptSubmit del filtro PII pre-Anthropic.

`process_prompt` recibe el input parseado del hook (dict con `prompt`,
`session_id`, `transcript_path`, `cwd`, `hook_event_name`) y devuelve un
dict que Claude Code interpreta:

- `{}` → no hay decisión, pasa el prompt sin modificar.
- `{"continue": True, "modified_prompt": "..."}` → reemplaza el prompt.

Override: si el prompt contiene `#fg-pass` (case-sensitive), se salta
todo análisis y se devuelve `{}` (el prompt pasa sin modificar).

Logging: redacciones y passthroughs se registran en `.forge/auditoria-pii.jsonl`.
Nada a loguear cuando no hay PII y no hay override.

ADR-4 (fail-open): si Presidio crashea, se devuelve `{}` y se loguea el
error en stderr. El filtro no bloquea el dev loop.
"""

import json
import os
import sys
from pathlib import Path

_FG_PASS_MARKER = "#fg-pass"


def _is_pii_disabled() -> bool:
    """Devuelve True si FORGE_PII_DISABLE tiene un valor truthy (no vacío, distinto de "0")."""
    val = os.environ.get("FORGE_PII_DISABLE", "")
    return bool(val) and val != "0"


def process_prompt(
    input_data: dict,
    *,
    analyzer=None,
    anonymizer=None,
    operators=None,
    log_path: Path | None = None,
) -> dict:
    """Procesa un payload del hook UserPromptSubmit de Claude Code.

    :param input_data: JSON parseado de stdin (debe contener la clave ``"prompt"``).
    :param analyzer: ``AnalyzerEngine`` inyectado (opcional; se construye lazy si es None).
    :param anonymizer: ``AnonymizerEngine`` inyectado (opcional; se construye lazy si es None).
    :param operators: dict de config de operators inyectado (opcional; se construye lazy si es None).
    :param log_path: Override del path del log (para tests). Default: ``.forge/auditoria-pii.jsonl``.
    :return: ``{}`` para no-op (pass-through) o
             ``{"continue": True, "modified_prompt": <redactado>}`` para redacciones.
    """
    # Paso 0: kill-switch FORGE_PII_DISABLE — se chequea ANTES de #fg-pass y de cualquier import de presidio
    if _is_pii_disabled():
        prompt = input_data.get("prompt", "")
        _log_passthrough(prompt, log_path)
        sys.stderr.write("[fg-pii] passthrough activo (FORGE_PII_DISABLE)\n")
        return {}

    prompt = input_data.get("prompt", "")

    # Paso 1: chequear el override #fg-pass ANTES de cualquier análisis (R20.5)
    if _FG_PASS_MARKER in prompt:
        _log_passthrough(prompt, log_path)
        sys.stderr.write("[fg-pii] passthrough activo (#fg-pass detectado)\n")
        return {}

    # Paso 2: import lazy de analyzer/anonymizer (ADR-3: optimización de cold start)
    if analyzer is None:
        from forge.filters.analyzer import build_analyzer

        analyzer = build_analyzer()
    if anonymizer is None or operators is None:
        from forge.filters.anonymizer import build_anonymizer

        anonymizer, operators = build_anonymizer()

    try:
        # Paso 3: analizar
        results = analyzer.analyze(text=prompt, language="en")

        # Paso 4: si no hay resultados, pasar sin modificar y en silencio (sin log)
        if not results:
            return {}

        # Paso 5: anonimizar
        anon_result = anonymizer.anonymize(
            text=prompt,
            analyzer_results=results,
            operators=operators,
        )
        modified_prompt = anon_result.text

        # Paso 6: loguear el evento de redacción
        types_count = _build_types_count(results)
        _log_redaction(prompt, types_count, log_path)

        # Paso 7: emitir nota a stderr
        total = sum(types_count.values())
        sorted_types = ", ".join(sorted(types_count.keys()))
        sys.stderr.write(f"[fg-pii] {total} dato(s) redactado(s): {sorted_types}\n")

        return {"continue": True, "modified_prompt": modified_prompt}

    except Exception as exc:  # noqa: BLE001
        # Fail-open: loguear el error a stderr, no bloquear el prompt
        sys.stderr.write(f"[fg-pii] error: {type(exc).__name__}\n")
        _log_error(prompt, log_path)
        return {}


def _build_types_count(results) -> dict:
    """Construye un dict que mapea tipos de entidad a su cantidad de ocurrencias."""
    types_count: dict = {}
    for result in results:
        types_count[result.entity_type] = types_count.get(result.entity_type, 0) + 1
    return types_count


def _log_redaction(prompt: str, types_count: dict, log_path: Path | None) -> None:
    """Agrega un evento de redacción al log JSONL."""
    from forge.filters.redaction_log import hash_prompt, log_event

    log_event(
        action="redacted",
        types=types_count,
        prompt_hash=hash_prompt(prompt),
        log_path=log_path,
    )


def _log_passthrough(prompt: str, log_path: Path | None) -> None:
    """Agrega un evento de passthrough al log JSONL."""
    from forge.filters.redaction_log import hash_prompt, log_event

    log_event(
        action="passthrough",
        types={},
        prompt_hash=hash_prompt(prompt),
        log_path=log_path,
    )


def _log_error(prompt: str, log_path: Path | None) -> None:
    """Agrega un evento de error al log JSONL (fail-open: traga cualquier error de logging)."""
    try:
        from forge.filters.redaction_log import hash_prompt, log_event

        log_event(
            action="error",
            types={},
            prompt_hash=hash_prompt(prompt),
            log_path=log_path,
        )
    except Exception:  # noqa: BLE001
        pass  # Fail-open: nunca dejar que el logging bloquee el hook


def main() -> int:
    """Entry point del hook UserPromptSubmit de Claude Code.

    Lee JSON de stdin, llama a process_prompt, escribe JSON a stdout.
    Siempre sale con 0 (fail-open según ADR-4).
    """
    try:
        raw = sys.stdin.buffer.read().decode("utf-8")
        input_data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        error_response = {"error": f"Failed to parse stdin: {type(exc).__name__}: {exc}"}
        sys.stdout.write(json.dumps(error_response))
        return 0  # Fail-open: exit 0 incluso si falla el parseo

    try:
        result = process_prompt(input_data)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[fg-pii] error: {type(exc).__name__}\n")
        result = {}

    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
