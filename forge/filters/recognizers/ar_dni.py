"""DNI_AR recognizer — Argentine national ID (REQ-REC-02).

Two-tier pattern:
- Formatted: ``\\d{1,2}\\.\\d{3}\\.\\d{3}`` — base score 0.7 (fires alone)
- Raw digits: ``\\b\\d{7,8}\\b`` — base score 0.3 (needs context to reach threshold)

Context words boost raw-digits pattern to >= 0.5 (above default threshold).
Arbitrary 7-8 digit integers without context do NOT fire at threshold 0.5.
"""

from presidio_analyzer import Pattern, PatternRecognizer

_DNI_CONTEXT = [
    "dni",
    "documento",
    "doc",
    "nro",
    "numero de documento",
    "identificacion",
    "identidad",
]


def build_dni_recognizer() -> PatternRecognizer:
    """Return a PatternRecognizer for Argentine DNI numbers.

    - Entity type: DNI_AR
    - Pattern 1 (formatted): ``\\d{1,2}\\.\\d{3}\\.\\d{3}`` — score 0.7
    - Pattern 2 (raw digits): ``\\b\\d{7,8}\\b`` — score 0.3
    - Context boost: ``dni``, ``documento``, etc. raise score to >= 0.5
    - No checksum (DNI has none)
    - No I/O side effects; importable without instantiating the full engine
    """
    patterns = [
        Pattern(
            name="dni_formatted",
            regex=r"\d{1,2}\.\d{3}\.\d{3}",
            score=0.7,
        ),
        Pattern(
            name="dni_raw",
            regex=r"\b\d{7,8}\b",
            score=0.3,
        ),
    ]
    return PatternRecognizer(
        supported_entity="DNI_AR",
        patterns=patterns,
        context=_DNI_CONTEXT,
        supported_language="en",
    )
