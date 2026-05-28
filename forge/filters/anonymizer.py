"""Anonymizer factory — Presidio AnonymizerEngine with type-specific placeholders (REQ-ANO-01).

Each entity type maps to a stable placeholder in [TYPE] format.
Conflict resolution (overlapping spans) is delegated to Presidio's built-in logic.
"""

from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# All 22 entity types (15 custom + 7 built-in)
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
    """Return (AnonymizerEngine, operators_config) with [TYPE] placeholders.

    operators_config is a dict mapping each of the 22 entity type labels to an
    OperatorConfig("replace", {"new_value": "[<TYPE>]"}).

    Calling this function multiple times is safe — no module-level state is mutated.
    """
    engine = AnonymizerEngine()
    operators = {
        entity_type: OperatorConfig("replace", {"new_value": f"[{entity_type}]"})
        for entity_type in _ENTITY_TYPES
    }
    return engine, operators
