"""Recognizer de CUIT — identificador tributario argentino (REQ-REC-01).

Formato CUIT: XX-XXXXXXXX-X (grupos de 2-8-1 dígitos separados por guiones).
Checksum: algoritmo mod-11 con pesos AFIP [5,4,3,2,7,6,5,4,3,2].
"""


from presidio_analyzer import Pattern, PatternRecognizer

_CUIT_WEIGHTS = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]

_CUIT_CONTEXT = [
    "cuit",
    "cuit_nro",
    "razon social",
    "proveedor",
    "contribuyente",
    "afip",
    "ruc",
]


def _is_valid_cuit(cuit_str: str) -> bool:
    """Valida el dígito verificador del CUIT con el algoritmo mod-11 (especificación AFIP)."""
    digits = cuit_str.replace("-", "")
    if len(digits) != 11:
        return False
    total = sum(int(digits[i]) * _CUIT_WEIGHTS[i] for i in range(10))
    remainder = total % 11
    check = 11 - remainder if remainder != 0 else 0
    if check == 11:
        check = 0
    if check == 10:
        # AFIP: esta combinación no produce un CUIT válido
        return False
    return check == int(digits[10])


class _CuitRecognizer(PatternRecognizer):
    """Subclase de PatternRecognizer que valida el checksum mod-11 del CUIT."""

    def validate_result(self, pattern_text: str) -> bool | None:
        """Devuelve True si el checksum pasa, False en caso contrario."""
        return _is_valid_cuit(pattern_text)


def build_cuit_recognizer() -> PatternRecognizer:
    """Devuelve un PatternRecognizer para números de CUIT argentinos.

    - Tipo de entidad: CUIT
    - Patrón: ``\\d{2}-\\d{8}-\\d`` (solo formateado, sin dígitos sueltos)
    - Score base: 0.85
    - Validador de checksum mod-11: los dígitos verificadores inválidos se descartan
    - Las palabras de contexto suben el score a 1.0
    - Sin efectos de I/O; importable sin instanciar el engine completo
    """
    pattern = Pattern(
        name="cuit_formatted",
        regex=r"\d{2}-\d{8}-\d",
        score=0.85,
    )
    return _CuitRecognizer(
        supported_entity="CUIT",
        patterns=[pattern],
        context=_CUIT_CONTEXT,
        supported_language="en",
    )
