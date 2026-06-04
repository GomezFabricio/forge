"""Portero proporcional — núcleo de decisión pura.

Función pura: no hace I/O, no lee filesystem, no pregunta al dev.
Toda la lógica de señales → nivel vive aquí para que Strict TDD
la pueda verificar sin montar el ciclo completo.

Precedencia de señales (ADR-4):
  1. threshold (override duro de proyecto)
  2. opt-in explícito del dev
  3. tipo inferido del cambio
  4. palabras de escala en la descripción
  Ambigüedad → Completo (regla conservadora, R-PORTERO-06)

Levels:
  "libre"    — forge no entra al ciclo
  "rapido"   — saltea solo /fg-design; /fg-review siempre corre (R-PORTERO-02)
  "completo" — ritual completo sin cambios
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constantes públicas
# ---------------------------------------------------------------------------

NIVEL_LIBRE = "libre"
NIVEL_RAPIDO = "rapido"
NIVEL_COMPLETO = "completo"

# Tipos que sesgan a Rápido (no implican diseño arquitectónico)
_TIPOS_LIGEROS = frozenset({"docs", "chore", "test", "style"})

# Palabras de escala que denotan un cambio grande (R-PORTERO-01)
_PALABRAS_ESCALA_DEFAULT = frozenset(
    {
        "migrar",
        "reemplazar",
        "rediseñar",
        "reescribir",
        "módulo de",
        "todo el",
        "sistema de",
    }
)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def decidir_nivel(senales: dict) -> dict:
    """Decide el nivel de ceremonia dado un conjunto de señales.

    Args:
        senales: dict con las claves:
            threshold (str):          "auto" | "lite" | "full"
            opt_in (str | None):      "rapido" | "libre" | "completo" | None
            tipo_inferido (str):      tipo conventional-commit inferido
            palabras_de_escala (list[str]): palabras presentes en la descripción
            arquitectura_al_dia (bool): resultado de check_arch_freshness()

    Returns:
        dict con las claves:
            nivel_propuesto (str):  "libre" | "rapido" | "completo"
            razon (str):            explicación legible de la decisión
            confianza (str):        "alta" | "media" | "baja"
    """
    threshold = senales.get("threshold", "auto")
    opt_in = senales.get("opt_in")
    tipo = (senales.get("tipo_inferido") or "feat").lower()
    palabras = senales.get("palabras_de_escala") or []
    arch_ok = senales.get("arquitectura_al_dia", True)

    # ------------------------------------------------------------------
    # Paso 1 — threshold es el override de máxima precedencia (R-PORTERO-05)
    # ------------------------------------------------------------------
    if threshold == "full":
        return _resultado(
            NIVEL_COMPLETO,
            "ceremonial_threshold=full: modo Completo forzado por configuración del proyecto",
            "alta",
        )

    # ------------------------------------------------------------------
    # Paso 2 — opt-in del dev (segunda prioridad, ADR-4)
    # ------------------------------------------------------------------
    if opt_in == "libre":
        return _resultado(NIVEL_LIBRE, "dev declaró modo Libre explícitamente", "alta")

    if opt_in in ("completo", "full"):
        return _resultado(
            NIVEL_COMPLETO,
            "dev declaró modo Completo explícitamente — se usa sin inferencia adicional",
            "alta",
        )

    if opt_in in ("rapido", "lite"):
        if not arch_ok:
            return _resultado(
                NIVEL_COMPLETO,
                "opt-in Rápido rechazado: arquitectura desactualizada, elevado a Completo",
                "alta",
            )
        # Verificar que no hay señales contradictorias (regla conservadora)
        if _tiene_palabras_de_escala(palabras):
            return _resultado(
                NIVEL_COMPLETO,
                "señales contradictorias: opt-in Rápido pero palabras de escala presentes — Completo por regla conservadora",
                "media",
            )
        return _resultado(
            NIVEL_RAPIDO,
            "opt-in Rápido del dev confirmado con arquitectura al día",
            "alta",
        )

    # ------------------------------------------------------------------
    # Paso 3 — inferencia por tipo y palabras de escala (sin opt-in)
    # ------------------------------------------------------------------

    # Palabras de escala: siempre fuerzan Completo (R-PORTERO-01)
    if _tiene_palabras_de_escala(palabras):
        return _resultado(
            NIVEL_COMPLETO,
            f"palabras de escala detectadas ({', '.join(palabras)}): cambio grande — Completo",
            "alta",
        )

    # threshold=lite sesga hacia Rápido para tipos ligeros con arch ok
    if threshold == "lite":
        if tipo in _TIPOS_LIGEROS and arch_ok:
            return _resultado(
                NIVEL_RAPIDO,
                f"threshold=lite + tipo '{tipo}' ligero + arquitectura al día → Rápido",
                "alta",
            )
        if not arch_ok:
            return _resultado(
                NIVEL_COMPLETO,
                "threshold=lite pero arquitectura desactualizada — Completo por seguridad",
                "alta",
            )
        # tipo no ligero (feat, refactor) con lite → Completo (tipo gana sobre lite)
        return _resultado(
            NIVEL_COMPLETO,
            f"threshold=lite pero tipo '{tipo}' no es trivial — Completo",
            "media",
        )

    # threshold=auto: tipos ligeros + arch ok → Rápido; resto → Completo
    if tipo in _TIPOS_LIGEROS:
        if arch_ok:
            return _resultado(
                NIVEL_RAPIDO,
                f"tipo '{tipo}' ligero + arquitectura al día → propone Rápido",
                "media",
            )
        return _resultado(
            NIVEL_COMPLETO,
            f"tipo '{tipo}' ligero pero arquitectura desactualizada — Completo",
            "alta",
        )

    # feat, refactor, u otro tipo pesado → Completo (regla conservadora)
    return _resultado(
        NIVEL_COMPLETO,
        f"tipo '{tipo}' implica cambio de comportamiento — Completo por regla conservadora",
        "alta",
    )


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _tiene_palabras_de_escala(palabras: list) -> bool:
    """Verifica si alguna palabra de la lista es una señal de escala conocida."""
    if not palabras:
        return False
    palabras_lower = {p.lower() for p in palabras}
    return bool(palabras_lower & _PALABRAS_ESCALA_DEFAULT)


def _resultado(nivel: str, razon: str, confianza: str) -> dict:
    """Construye el dict de retorno estándar."""
    return {
        "nivel_propuesto": nivel,
        "razon": razon,
        "confianza": confianza,
    }
