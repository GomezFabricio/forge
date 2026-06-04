"""Detector de arquitectura al día — heurística de drift por frontmatter.

Mecanismo (ADR-1): escanea docs/auditoria/cambios/*/README.md buscando
cambios con frontmatter `structural: true` que NO tengan `arch_synced: true`.
Si existe al menos uno → arquitectura DESACTUALIZADA.

Limitación declarada: solo detecta drift de cambios que pasaron por forge
y fueron marcados structural. NO detecta cambios manuales externos.
Es una señal de piso, no de techo — si dice desactualizada, lo está;
si dice al día, es "al día hasta donde forge sabe".

Dependencias: solo stdlib (pathlib, re) — sin dependencias extras.
"""

from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def check_arch_freshness(
    cambios_dir: Path,
    arch_overview: Path,
) -> dict:
    """Verifica si la arquitectura documentada está al día.

    Args:
        cambios_dir:   Ruta a docs/auditoria/cambios/ (puede no existir).
        arch_overview: Ruta a docs/arquitectura/overview.md.

    Returns:
        dict con las claves:
            al_dia (bool):       True si no hay cambios estructurales pendientes
                                 de sincronizar y overview.md existe.
            pendientes (int):    Número de cambios structural sin arch_synced.
            sin_overview (bool): True si overview.md no existe.
    """
    # Guard mínimo de existencia: sin overview.md → no al día (ADR-1)
    if not arch_overview.exists():
        return {"al_dia": False, "pendientes": 0, "sin_overview": True}

    pendientes = _contar_pendientes(cambios_dir)

    return {
        "al_dia": pendientes == 0,
        "pendientes": pendientes,
        "sin_overview": False,
    }


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _contar_pendientes(cambios_dir: Path) -> int:
    """Cuenta los READMEs con structural=true y sin arch_synced=true."""
    if not cambios_dir.exists():
        return 0

    pendientes = 0
    for readme in cambios_dir.glob("*/README.md"):
        frontmatter = _leer_frontmatter(readme)
        if frontmatter is None:
            continue
        if _es_structural_pendiente(frontmatter):
            pendientes += 1

    return pendientes


_RE_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_RE_CLAVE_VALOR = re.compile(r"^(\w[\w_]*):\s*(.+)$", re.MULTILINE)


def _leer_frontmatter(readme: Path) -> dict | None:
    """Extrae el frontmatter YAML del README. Retorna None si no hay frontmatter."""
    try:
        texto = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    match = _RE_FRONTMATTER.match(texto)
    if not match:
        return None

    bloque = match.group(1)
    campos: dict = {}
    for m in _RE_CLAVE_VALOR.finditer(bloque):
        clave = m.group(1)
        valor_str = m.group(2).strip().lower()
        # Parseo simple de bool YAML
        if valor_str in ("true", "yes"):
            campos[clave] = True
        elif valor_str in ("false", "no"):
            campos[clave] = False
        else:
            campos[clave] = valor_str

    return campos


def _es_structural_pendiente(frontmatter: dict) -> bool:
    """Retorna True si el cambio es estructural y no tiene arch_synced=true."""
    es_structural = frontmatter.get("structural") is True
    ya_sincronizado = frontmatter.get("arch_synced") is True
    return es_structural and not ya_sincronizado
