"""Helpers del log de redacción (REQ-LOG-01).

Escribe JSONL append-only en .forge/auditoria-pii.jsonl.
Nunca guarda el contenido del prompt — solo un hash SHA-256 (truncado a 16 chars).
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from forge import __version__ as _FORGE_VERSION
except ImportError:
    _FORGE_VERSION = "unknown"

_DEFAULT_LOG_PATH = Path(".forge") / "auditoria-pii.jsonl"


def hash_prompt(prompt: str) -> str:
    """Devuelve los primeros 16 caracteres hex del digest SHA-256 de prompt.

    Alcanza para correlacionar eventos sin permitir re-identificación.
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
    """Agrega un evento de redacción o passthrough al archivo de log JSONL.

    :param action: Uno de ``"redacted"``, ``"passthrough"``, ``"error"``.
    :param types: Dict que mapea labels de tipo de entidad a su cantidad de ocurrencias.
                  Dict vacío para eventos passthrough/error.
    :param prompt_hash: String hex de 16 caracteres (SHA-256[:16] del prompt original).
    :param log_path: Override del path del log. Default: ``.forge/auditoria-pii.jsonl``
                     relativo al cwd. El override se usa en tests vía ``tmp_path``.
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

    # Abrir en modo append con line endings LF explícitos (sin CRLF en Windows)
    with open(log_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry) + "\n")
