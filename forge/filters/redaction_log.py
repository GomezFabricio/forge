"""Redaction log helpers (REQ-LOG-01).

Writes append-only JSONL to .forge/redactions.jsonl.
Never stores prompt content — only a SHA-256 hash (truncated to 16 chars).
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from forge import __version__ as _FORGE_VERSION
except ImportError:
    _FORGE_VERSION = "unknown"

_DEFAULT_LOG_PATH = Path(".forge") / "redactions.jsonl"


def hash_prompt(prompt: str) -> str:
    """Return the first 16 hex characters of the SHA-256 digest of prompt.

    This is sufficient for event correlation without enabling re-identification.
    """
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return digest[:16]


def log_event(
    *,
    action: str,
    types: dict,
    prompt_hash: str,
    log_path: Path | None = None,
) -> None:
    """Append a redaction or passthrough event to the JSONL log file.

    :param action: One of ``"redacted"``, ``"passthrough"``, ``"error"``.
    :param types: Dict mapping entity type labels to their occurrence count.
                  Empty dict for passthrough/error events.
    :param prompt_hash: 16-character hex string (SHA-256[:16] of original prompt).
    :param log_path: Override log file path. Defaults to ``.forge/redactions.jsonl``
                     relative to cwd. Override is used in tests via ``tmp_path``.
    """
    if log_path is None:
        log_path = _DEFAULT_LOG_PATH

    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    count = sum(types.values()) if types else 0
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

    entry = {
        "ts": ts,
        "action": action,
        "types": types,
        "count": count,
        "prompt_hash": prompt_hash,
        "version": _FORGE_VERSION,
    }

    # Open in append mode with explicit LF line endings (no CRLF on Windows)
    with open(log_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry) + "\n")
