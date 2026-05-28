"""CBU recognizer — Argentine bank account code (REQ-REC-03).

CBU format: 22 digits. Two-block checksum algorithm (BCRA specification):
- Block 1: first 7 digits with weights [3,1,7,9,3,1,7], check at position 7
- Block 2: digits 8-20 (13 digits) with weights [9,1,7,3,9,1,7,3,9,1,7,3,9], check at pos 21

check_digit = (10 - (sum_of_weighted_digits % 10)) % 10
"""


from presidio_analyzer import Pattern, PatternRecognizer

_BLOCK1_WEIGHTS = [3, 1, 7, 9, 3, 1, 7]
_BLOCK2_WEIGHTS = [9, 1, 7, 3, 9, 1, 7, 3, 9, 1, 7, 3, 9]


def _cbu_check_digit(digits: str, weights: list) -> int:
    """Compute expected check digit for a CBU block."""
    total = sum(int(d) * w for d, w in zip(digits, weights, strict=True))
    return (10 - (total % 10)) % 10


def _is_valid_cbu(cbu_str: str) -> bool:
    """Validate both CBU blocks using BCRA checksum algorithm."""
    if len(cbu_str) != 22:
        return False
    try:
        # Block 1: first 7 digits + check at index 7
        expected1 = _cbu_check_digit(cbu_str[:7], _BLOCK1_WEIGHTS)
        if expected1 != int(cbu_str[7]):
            return False
        # Block 2: digits at indices 8-20 (13 digits) + check at index 21
        expected2 = _cbu_check_digit(cbu_str[8:21], _BLOCK2_WEIGHTS)
        if expected2 != int(cbu_str[21]):
            return False
    except (ValueError, IndexError):
        return False
    return True


class _CbuRecognizer(PatternRecognizer):
    """PatternRecognizer subclass that validates the CBU two-block checksum."""

    def validate_result(self, pattern_text: str) -> bool | None:
        """Return True if both block checksums pass, False otherwise."""
        return _is_valid_cbu(pattern_text)


def build_cbu_recognizer() -> PatternRecognizer:
    """Return a PatternRecognizer for Argentine CBU codes.

    - Entity type: CBU
    - Pattern: ``\\b\\d{22}\\b`` (exact 22 digits)
    - Base score: 0.85
    - Two-block BCRA checksum validator: invalid checksums are discarded
    - No context required (high specificity from 22-digit + checksum)
    - No I/O side effects; importable without instantiating the full engine
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
