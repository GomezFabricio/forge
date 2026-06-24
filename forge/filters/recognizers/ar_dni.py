"""Recognizer de DNI_AR — documento nacional de identidad argentino (REQ-REC-02).

Patrón de dos niveles:
- Formateado: ``\\d{1,2}\\.\\d{3}\\.\\d{3}`` — score base 0.7 (dispara solo)
- Dígitos sueltos: ``\\b\\d{7,8}\\b`` — score base 0.3 (necesita contexto para llegar al umbral)

Las palabras de contexto suben el patrón de dígitos sueltos a >= 0.5 (sobre el umbral default).
Enteros arbitrarios de 7-8 dígitos sin contexto NO disparan con el umbral 0.5.
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
    """Devuelve un PatternRecognizer para números de DNI argentinos.

    - Tipo de entidad: DNI_AR
    - Patrón 1 (formateado): ``\\d{1,2}\\.\\d{3}\\.\\d{3}`` — score 0.7
    - Patrón 2 (dígitos sueltos): ``\\b\\d{7,8}\\b`` — score 0.3
    - Boost de contexto: ``dni``, ``documento``, etc. suben el score a >= 0.5
    - Sin checksum (el DNI no tiene)
    - Sin efectos de I/O; importable sin instanciar el engine completo
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
