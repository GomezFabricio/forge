"""Recognizer de CBU — código de cuenta bancaria argentino (REQ-REC-03).

Formato CBU: 22 dígitos. Algoritmo de checksum de dos bloques (especificación BCRA):
- Bloque 1: primeros 7 dígitos con pesos [3,1,7,9,3,1,7], verificador en la posición 7
- Bloque 2: dígitos 8-20 (13 dígitos) con pesos [9,1,7,3,9,1,7,3,9,1,7,3,9], verificador en la pos 21

check_digit = (10 - (suma_de_dígitos_ponderados % 10)) % 10
"""


from presidio_analyzer import Pattern, PatternRecognizer

_BLOCK1_WEIGHTS = [3, 1, 7, 9, 3, 1, 7]
_BLOCK2_WEIGHTS = [9, 1, 7, 3, 9, 1, 7, 3, 9, 1, 7, 3, 9]


def _cbu_check_digit(digits: str, weights: list) -> int:
    """Calcula el dígito verificador esperado para un bloque del CBU."""
    total = sum(int(d) * w for d, w in zip(digits, weights, strict=True))
    return (10 - (total % 10)) % 10


def _is_valid_cbu(cbu_str: str) -> bool:
    """Valida ambos bloques del CBU con el algoritmo de checksum del BCRA."""
    if len(cbu_str) != 22:
        return False
    try:
        # Bloque 1: primeros 7 dígitos + verificador en el índice 7
        expected1 = _cbu_check_digit(cbu_str[:7], _BLOCK1_WEIGHTS)
        if expected1 != int(cbu_str[7]):
            return False
        # Bloque 2: dígitos en los índices 8-20 (13 dígitos) + verificador en el índice 21
        expected2 = _cbu_check_digit(cbu_str[8:21], _BLOCK2_WEIGHTS)
        if expected2 != int(cbu_str[21]):
            return False
    except (ValueError, IndexError):
        return False
    return True


class _CbuRecognizer(PatternRecognizer):
    """Subclase de PatternRecognizer que valida el checksum de dos bloques del CBU."""

    def validate_result(self, pattern_text: str) -> bool | None:
        """Devuelve True si ambos checksums de bloque pasan, False en caso contrario."""
        return _is_valid_cbu(pattern_text)


def build_cbu_recognizer() -> PatternRecognizer:
    """Devuelve un PatternRecognizer para códigos CBU argentinos.

    - Tipo de entidad: CBU
    - Patrón: ``\\b\\d{22}\\b`` (exactamente 22 dígitos)
    - Score base: 0.85
    - Validador de checksum BCRA de dos bloques: los checksums inválidos se descartan
    - No requiere contexto (alta especificidad por los 22 dígitos + checksum)
    - Sin efectos de I/O; importable sin instanciar el engine completo
    """
    pattern = Pattern(
        name="cbu_22digits",
        regex=r"\b\d{22}\b",
        score=0.85,
    )
    return _CbuRecognizer(
        supported_entity="CBU",
        patterns=[pattern],
        supported_language="en",
    )
