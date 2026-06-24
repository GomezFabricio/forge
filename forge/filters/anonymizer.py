"""Fábrica del anonimizador — AnonymizerEngine de Presidio con placeholders por tipo (REQ-ANO-01).

Cada tipo de entidad se mapea a un placeholder estable con el formato [TIPO].
La resolución de conflictos (spans solapados) se delega en la lógica interna de Presidio.
"""

from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# Los 22 tipos de entidad (15 custom + 7 built-in)
_ENTITY_TYPES = [
    "CUIT",
    "DNI_AR",
    "CBU",
    "JWT",
    "AWS_ACCESS_KEY",
    "AWS_SECRET_KEY",
    "GITHUB_PAT",
    "GITHUB_FINE_GRAINED",
    "OPENAI_KEY",
    "ANTHROPIC_KEY",
    "SLACK_TOKEN",
    "STRIPE_KEY",
    "PRIVATE_KEY_BLOCK",
    "CONNECTION_STRING_PASSWORD",
    "BEARER_TOKEN",
    "CREDIT_CARD",
    "EMAIL_ADDRESS",
    "IBAN_CODE",
    "IP_ADDRESS",
    "PHONE_NUMBER",
    "URL",
    "CRYPTO",
]


def build_anonymizer() -> tuple:
    """Devuelve (AnonymizerEngine, operators_config) con placeholders [TIPO].

    operators_config es un dict que mapea cada uno de los 22 labels de tipo de
    entidad a un OperatorConfig("replace", {"new_value": "[<TIPO>]"}).

    Llamar a esta función varias veces es seguro — no muta estado a nivel módulo.
    """
    engine = AnonymizerEngine()
    operators = {
        entity_type: OperatorConfig("replace", {"new_value": f"[{entity_type}]"})
        for entity_type in _ENTITY_TYPES
    }
    return engine, operators
