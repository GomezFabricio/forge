"""Tests para forge.portero_decision — función pura decidir_nivel.

Cubre los escenarios definidos en el spec R-PORTERO-01, R-PORTERO-03,
R-PORTERO-05 y R-PORTERO-06.

Precedencia de señales (ADR-4):
  threshold > opt-in > tipo > palabras_de_escala
  Ambigüedad → Completo (regla conservadora).
"""

from forge.portero_decision import decidir_nivel

# ---------------------------------------------------------------------------
# Constantes de salida esperada
# ---------------------------------------------------------------------------

COMPLETO = "completo"
RAPIDO = "rapido"
LIBRE = "libre"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _senales_base(**kwargs):
    """Señales con valores neutrales; sobreescribir lo que el test necesite."""
    base = {
        "threshold": "auto",
        "opt_in": None,
        "tipo_inferido": "feat",
        "palabras_de_escala": [],
        "arquitectura_al_dia": True,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# R-PORTERO-05 — threshold fuerza el nivel
# ---------------------------------------------------------------------------


class TestThreshold:
    """El campo ceremonial_threshold es el override de máxima precedencia."""

    def test_threshold_full_con_senales_rapido_retorna_completo(self):
        """GIVEN threshold=full + señales de Rápido → THEN Completo sin excepción."""
        senales = _senales_base(
            threshold="full",
            opt_in="rapido",
            tipo_inferido="docs",
            arquitectura_al_dia=True,
        )
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == COMPLETO

    def test_threshold_full_razon_explicita(self):
        """GIVEN threshold=full → THEN la razón menciona el threshold."""
        senales = _senales_base(threshold="full")
        resultado = decidir_nivel(senales)
        assert "threshold" in resultado["razon"].lower()

    def test_threshold_lite_arquitectura_al_dia_tipo_docs_retorna_rapido(self):
        """GIVEN threshold=lite + arquitectura al día + tipo=docs → Rápido."""
        senales = _senales_base(
            threshold="lite",
            tipo_inferido="docs",
            arquitectura_al_dia=True,
        )
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == RAPIDO

    def test_threshold_lite_arquitectura_desactualizada_retorna_completo(self):
        """GIVEN threshold=lite + arquitectura desactualizada → THEN Completo (seguridad)."""
        senales = _senales_base(
            threshold="lite",
            tipo_inferido="docs",
            arquitectura_al_dia=False,
        )
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == COMPLETO

    def test_threshold_auto_sigue_inferencia_normal(self):
        """GIVEN threshold=auto → el portero infiere según las otras señales."""
        senales = _senales_base(
            threshold="auto",
            opt_in="rapido",
            tipo_inferido="docs",
            arquitectura_al_dia=True,
        )
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == RAPIDO


# ---------------------------------------------------------------------------
# R-PORTERO-01 / R-PORTERO-06 — opt-in + tipo + palabras de escala
# ---------------------------------------------------------------------------


class TestOptIn:
    """El dev declara; el portero no adivina (ADR-4: opt-in > tipo > palabras)."""

    def test_opt_in_rapido_con_arquitectura_al_dia_retorna_rapido(self):
        """GIVEN opt_in=rapido + arquitectura al día → propone Rápido."""
        senales = _senales_base(opt_in="rapido", arquitectura_al_dia=True)
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == RAPIDO

    def test_opt_in_rapido_con_arquitectura_desactualizada_retorna_completo(self):
        """GIVEN opt_in=rapido + arquitectura desactualizada → eleva a Completo."""
        senales = _senales_base(opt_in="rapido", arquitectura_al_dia=False)
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == COMPLETO

    def test_opt_in_rapido_arquitectura_desactualizada_razon_menciona_arch(self):
        """GIVEN opt_in=rapido + arch desactualizada → THEN razón explica el override."""
        senales = _senales_base(opt_in="rapido", arquitectura_al_dia=False)
        resultado = decidir_nivel(senales)
        razon = resultado["razon"].lower()
        assert "arquitectura" in razon or "arch" in razon

    def test_opt_in_libre_retorna_libre(self):
        """GIVEN opt_in=libre → nivel Libre."""
        senales = _senales_base(opt_in="libre")
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == LIBRE


class TestTipoInferido:
    """El tipo inferido sesga la decisión cuando no hay opt-in."""

    def test_tipo_feat_sin_optin_retorna_completo(self):
        """GIVEN tipo=feat sin opt-in → sesgo Completo."""
        senales = _senales_base(tipo_inferido="feat", opt_in=None)
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == COMPLETO

    def test_tipo_docs_sin_optin_arquitectura_al_dia_retorna_rapido(self):
        """GIVEN tipo=docs sin opt-in + arch al día → propone Rápido."""
        senales = _senales_base(
            tipo_inferido="docs",
            opt_in=None,
            arquitectura_al_dia=True,
        )
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == RAPIDO

    def test_tipo_chore_sin_optin_arquitectura_al_dia_retorna_rapido(self):
        """GIVEN tipo=chore sin opt-in + arch al día → propone Rápido."""
        senales = _senales_base(
            tipo_inferido="chore",
            opt_in=None,
            arquitectura_al_dia=True,
        )
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == RAPIDO


class TestPalabrasDeEscala:
    """Palabras de escala fuerzan Completo independientemente del tipo."""

    def test_palabras_de_escala_migrar_con_tipo_feat_retorna_completo(self):
        """GIVEN tipo=feat + palabras_de_escala=[migrar] → Completo."""
        senales = _senales_base(
            tipo_inferido="feat",
            palabras_de_escala=["migrar"],
            opt_in=None,
        )
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == COMPLETO

    def test_palabras_de_escala_varias_retorna_completo(self):
        """GIVEN palabras de escala presentes → siempre Completo."""
        for palabra in ["reemplazar", "rediseñar", "reescribir"]:
            senales = _senales_base(
                tipo_inferido="docs",
                palabras_de_escala=[palabra],
                opt_in=None,
                arquitectura_al_dia=True,
            )
            resultado = decidir_nivel(senales)
            assert resultado["nivel_propuesto"] == COMPLETO, (
                f"Esperaba Completo con palabra '{palabra}'"
            )


# ---------------------------------------------------------------------------
# R-PORTERO-06 — regla conservadora ante señales contradictorias
# ---------------------------------------------------------------------------


class TestReglaConservadora:
    """Sin CodeGraph, la ambigüedad se resuelve conservadoramente → Completo."""

    def test_senales_contradictorias_opt_in_rapido_palabras_escala_retorna_completo(
        self,
    ):
        """GIVEN opt_in=rapido + palabras_de_escala presentes → señales contradictorias → Completo."""
        senales = _senales_base(
            opt_in="rapido",
            palabras_de_escala=["migrar"],
            tipo_inferido="feat",
            arquitectura_al_dia=True,
        )
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == COMPLETO

    def test_resultado_tiene_confianza(self):
        """Cada resultado expone campo 'confianza'."""
        senales = _senales_base()
        resultado = decidir_nivel(senales)
        assert "confianza" in resultado

    def test_resultado_tiene_razon(self):
        """Cada resultado expone campo 'razon' no vacío."""
        senales = _senales_base()
        resultado = decidir_nivel(senales)
        assert resultado["razon"]


# ---------------------------------------------------------------------------
# R-PORTERO-03 — arquitectura al día como condición habilitante de Rápido
# ---------------------------------------------------------------------------


class TestArquitecturaAlDia:
    """La condición 'arquitectura al día' puede bloquear Rápido incluso con señales favorables."""

    def test_threshold_lite_arch_al_dia_tipo_feat_retorna_completo(self):
        """GIVEN threshold=lite + tipo=feat + arch al día → feat sigue sesgando Completo."""
        senales = _senales_base(
            threshold="lite",
            tipo_inferido="feat",
            opt_in=None,
            arquitectura_al_dia=True,
        )
        resultado = decidir_nivel(senales)
        # feat sesga Completo incluso con lite (solo docs/chore admiten Rápido con lite)
        assert resultado["nivel_propuesto"] == COMPLETO

    def test_threshold_auto_arch_desactualizada_tipo_docs_retorna_completo(self):
        """GIVEN threshold=auto + tipo=docs + arch desactualizada → forzado a Completo."""
        senales = _senales_base(
            threshold="auto",
            tipo_inferido="docs",
            opt_in=None,
            arquitectura_al_dia=False,
        )
        resultado = decidir_nivel(senales)
        assert resultado["nivel_propuesto"] == COMPLETO
