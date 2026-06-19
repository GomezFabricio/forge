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

# ReDoS mitigation (Task B / ADR-4 defense-in-depth).
#
# A user-authored guardrails.yaml may contain a pattern vulnerable to
# catastrophic backtracking (e.g. ``(a+)+$``). The cost of such backtracking
# scales with the length of the INPUT, not the pattern: a longer command can
# turn a slow match into one that spins for tens of seconds, stalling the dev
# loop. That is worse than an exception (which fails open instantly) because a
# hung process keeps Claude Code waiting — defeating the ADR-4 intent of never
# blocking the loop.
#
# We bound the command string fed to every regex to MAX_COMMAND_LEN characters.
# Truncating the input caps the worst-case backtracking cost to a fixed ceiling
# regardless of the pattern, on both Windows and Unix, with zero extra threads
# or signals. A real per-evaluation timeout was evaluated and rejected: a
# ``threading``-based join cannot interrupt a CPU-bound ``re.search`` under
# CPython because the regex engine holds the GIL while matching (measured: a
# 2s join returned only after ~23s), so it would provide false safety. The
# length cap is therefore the primary, and only reliable, mitigation here.
#
# Residual risk (accepted, documented): a pathological pattern whose blow-up
# threshold is BELOW MAX_COMMAND_LEN can still be slow on a short command. The
# guard is best-effort; a catastrophic user-authored pattern remains the user's
# responsibility (see README "Defensa en profundidad" / guia-de-uso §6).
# 8192 chars comfortably covers realistic Bash one-liners while keeping the
# truncated-input backtracking cost negligible (measured sub-millisecond).
MAX_COMMAND_LEN = 8192


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
    # ReDoS mitigation: bound the input fed to every regex (see MAX_COMMAND_LEN).
    # The hash used for the audit log is computed over the FULL command upstream,
    # so correlation is unaffected; only the matched text is capped.
    match_target = command[:MAX_COMMAND_LEN]

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

        if not regex.search(match_target):
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


def _resolve_log_path(input_data: dict, log_path: Path | None) -> Path | None:
    """Best-effort guard log path for the error-audit paths (fail-open).

    Returns the explicit override if given; otherwise derives it from the
    payload cwd. Returns None when no location can be determined, in which case
    the caller silently skips the audit (never raises). Swallows all errors.
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
    """Core hook logic. May raise — wrapped by process_hook's fail-open guard."""
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


def process_hook(input_data: dict, *, log_path: Path | None = None) -> dict:
    """Process a Claude Code PreToolUse hook payload.

    Fail-open guard (ADR-4): any unexpected exception is swallowed, returns {}.
    Unlike a bare swallow, an unexpected failure here ALSO leaves a
    machine-readable audit trace (``action="error"``) so escaped exceptions are
    not invisible. The audit line carries only the exception TYPE name as a
    stable marker — never the raw command — preserving the privacy contract.

    :param input_data: Parsed JSON from stdin.
    :param log_path: Override log file path (for tests).
    :returns: Decision dict or {} (no decision = normal permission flow).
    """
    try:
        return _process_hook_inner(input_data, log_path=log_path)
    except Exception as exc:  # noqa: BLE001
        # D3: emit a machine-readable audit record on the error path. Use only
        # the exception type name as a stable marker — do NOT include the raw
        # command or the exception args (which could echo input).
        audit_path = _resolve_log_path(input_data, log_path)
        if audit_path is not None:
            _log_error(
                message=f"unexpected error in process_hook: {type(exc).__name__}",
                log_path=audit_path,
            )
        return {}  # Fail-open: never re-raise, never exit non-zero


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
        # Backstop: process_hook owns its own fail-open audit, but if it ever
        # raises before that guard runs, still leave a machine-readable trace
        # here (action="error", type-name marker only — never the raw command).
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
