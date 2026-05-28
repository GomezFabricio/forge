"""CUIT recognizer — Argentine tax ID (REQ-REC-01).

CUIT format: XX-XXXXXXXX-X (2-8-1 digit groups separated by hyphens).
Checksum: mod-11 algorithm with AFIP weights [5,4,3,2,7,6,5,4,3,2].
"""

from typing import Optional

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
    """Validate CUIT check digit via mod-11 algorithm (AFIP specification)."""
    digits = cuit_str.replace("-", "")
    if len(digits) != 11:
        return False
    total = sum(int(digits[i]) * _CUIT_WEIGHTS[i] for i in range(10))
    remainder = total % 11
    check = 11 - remainder if remainder != 0 else 0
    if check == 11:
        check = 0
    if check == 10:
        # AFIP: this combination yields no valid CUIT
        return False
    return check == int(digits[10])


class _CuitRecognizer(PatternRecognizer):
    """PatternRecognizer subclass that validates the CUIT mod-11 checksum."""

    def validate_result(self, pattern_text: str) -> Optional[bool]:
        """Return True if checksum passes, False otherwise."""
        return _is_valid_cuit(pattern_text)


def build_cuit_recognizer() -> PatternRecognizer:
    """Return a PatternRecognizer for Argentine CUIT numbers.

    - Entity type: CUIT
    - Pattern: ``\\d{2}-\\d{8}-\\d`` (formatted only, no raw digits)
    - Base score: 0.85
    - Mod-11 checksum validator: invalid check digits are discarded
    - Context words boost score to 1.0
    - No I/O side effects; importable without instantiating the full engine
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
