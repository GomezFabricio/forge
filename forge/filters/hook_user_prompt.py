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
import sys
from pathlib import Path

_FG_PASS_MARKER = "#fg-pass"


def process_prompt(
    input_data: dict,
    *,
    analyzer=None,
    anonymizer=None,
    operators=None,
    log_path: Path | None = None,
) -> dict:
    """Process a Claude Code UserPromptSubmit hook payload.

    :param input_data: Parsed JSON from stdin (must contain ``"prompt"`` key).
    :param analyzer: Injected ``AnalyzerEngine`` (optional; lazy-built if None).
    :param anonymizer: Injected ``AnonymizerEngine`` (optional; lazy-built if None).
    :param operators: Injected operators config dict (optional; lazy-built if None).
    :param log_path: Override log file path (for tests). Defaults to ``.forge/auditoria-pii.jsonl``.
    :return: ``{}`` for no-op (pass-through) or
             ``{"continue": True, "modified_prompt": <redacted>}`` for redactions.
    """
    prompt = input_data.get("prompt", "")

    # Step 1: check #fg-pass override BEFORE any analysis (R20.5)
    if _FG_PASS_MARKER in prompt:
        _log_passthrough(prompt, log_path)
        sys.stderr.write("[fg-pii] passthrough activo (#fg-pass detectado)\n")
        return {}

    # Step 2: lazy-import analyzer/anonymizer (ADR-3: cold start optimization)
    if analyzer is None:
        from forge.filters.analyzer import build_analyzer

        analyzer = build_analyzer()
    if anonymizer is None or operators is None:
        from forge.filters.anonymizer import build_anonymizer

        anonymizer, operators = build_anonymizer()

    try:
        # Step 3: analyze
        results = analyzer.analyze(text=prompt, language="en")

        # Step 4: if no results, pass through silently (no log)
        if not results:
            return {}

        # Step 5: anonymize
        anon_result = anonymizer.anonymize(
            text=prompt,
            analyzer_results=results,
            operators=operators,
        )
        modified_prompt = anon_result.text

        # Step 6: log redaction event
        types_count = _build_types_count(results)
        _log_redaction(prompt, types_count, log_path)

        # Step 7: emit stderr note
        total = sum(types_count.values())
        sorted_types = ", ".join(sorted(types_count.keys()))
        sys.stderr.write(f"[fg-pii] {total} dato(s) redactado(s): {sorted_types}\n")

        return {"continue": True, "modified_prompt": modified_prompt}

    except Exception as exc:  # noqa: BLE001
        # Fail-open: log error to stderr, do not block the prompt
        sys.stderr.write(f"[fg-pii] error: {type(exc).__name__}\n")
        return {}


def _build_types_count(results) -> dict:
    """Build a dict mapping entity types to their occurrence counts."""
    types_count: dict = {}
    for result in results:
        types_count[result.entity_type] = types_count.get(result.entity_type, 0) + 1
    return types_count


def _log_redaction(prompt: str, types_count: dict, log_path: Path | None) -> None:
    """Append a redaction event to the JSONL log."""
    from forge.filters.redaction_log import hash_prompt, log_event

    log_event(
        action="redacted",
        types=types_count,
        prompt_hash=hash_prompt(prompt),
        log_path=log_path,
    )


def _log_passthrough(prompt: str, log_path: Path | None) -> None:
    """Append a passthrough event to the JSONL log."""
    from forge.filters.redaction_log import hash_prompt, log_event

    log_event(
        action="passthrough",
        types={},
        prompt_hash=hash_prompt(prompt),
        log_path=log_path,
    )


def main() -> int:
    """Entry point for Claude Code UserPromptSubmit hook.

    Reads JSON from stdin, calls process_prompt, writes JSON to stdout.
    Always exits 0 (fail-open per ADR-4).
    """
    try:
        raw = sys.stdin.buffer.read().decode("utf-8")
        input_data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        error_response = {"error": f"Failed to parse stdin: {type(exc).__name__}: {exc}"}
        sys.stdout.write(json.dumps(error_response))
        return 0  # Fail-open: exit 0 even on parse error

    try:
        result = process_prompt(input_data)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[fg-pii] error: {type(exc).__name__}\n")
        result = {}

    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
