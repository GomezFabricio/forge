"""Tests del anonymizer factory (REQ-ANO-01).

TDD cycle: RED — imports build_anonymizer which does not exist yet.
"""

from forge.filters.analyzer import build_analyzer
from forge.filters.anonymizer import build_anonymizer
from tests.filters.fixtures import CUIT_VALID_1, GITHUB_CLASSIC_PAT

_ALL_22_ENTITY_TYPES = [
    "CUIT", "DNI_AR", "CBU", "JWT", "AWS_ACCESS_KEY", "AWS_SECRET_KEY",
    "GITHUB_PAT", "GITHUB_FINE_GRAINED", "OPENAI_KEY", "ANTHROPIC_KEY",
    "SLACK_TOKEN", "STRIPE_KEY", "PRIVATE_KEY_BLOCK", "CONNECTION_STRING_PASSWORD",
    "BEARER_TOKEN", "CREDIT_CARD", "EMAIL_ADDRESS", "IBAN_CODE", "IP_ADDRESS",
    "PHONE_NUMBER", "URL", "CRYPTO",
]


class TestBuildAnonymizer:
    """Tests for build_anonymizer() — REQ-ANO-01."""

    def test_all_22_operators_present(self):
        """R17.1: operators_config contains all 22 entity type keys."""
        _, operators = build_anonymizer()
        missing = [t for t in _ALL_22_ENTITY_TYPES if t not in operators]
        assert missing == [], f"Missing operators for: {missing}"

    def test_placeholder_format(self):
        """R17.2: each placeholder is [TYPE] format."""
        _, operators = build_anonymizer()
        for entity_type in _ALL_22_ENTITY_TYPES:
            op = operators[entity_type]
            new_value = op.params["new_value"]
            assert new_value == f"[{entity_type}]", (
                f"Expected [{entity_type}], got {new_value}"
            )

    def test_single_entity_replaced(self):
        """ANO-01-A: single CUIT entity is replaced with [CUIT] placeholder."""
        analyzer = build_analyzer()
        anonymizer_engine, operators = build_anonymizer()

        text = f"Mi CUIT es {CUIT_VALID_1} y necesito facturar"
        results = analyzer.analyze(text=text, language="en")
        anon_result = anonymizer_engine.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        assert "[CUIT]" in anon_result.text
        assert CUIT_VALID_1 not in anon_result.text

    def test_surrounding_text_preserved(self):
        """R17.3: surrounding text is preserved verbatim."""
        analyzer = build_analyzer()
        anonymizer_engine, operators = build_anonymizer()

        text = f"Mi CUIT es {CUIT_VALID_1} y necesito facturar"
        results = analyzer.analyze(text=text, language="en")
        anon_result = anonymizer_engine.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        assert "Mi CUIT es" in anon_result.text
        assert "y necesito facturar" in anon_result.text

    def test_multi_entity_prompt(self):
        """ANO-01-B: multiple entity types in one prompt are all replaced."""
        analyzer = build_analyzer()
        anonymizer_engine, operators = build_anonymizer()

        text = f"Email: user@example.com, token: {GITHUB_CLASSIC_PAT}"
        results = analyzer.analyze(text=text, language="en")
        anon_result = anonymizer_engine.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        assert "[EMAIL_ADDRESS]" in anon_result.text
        assert "[GITHUB_PAT]" in anon_result.text
        assert "user@example.com" not in anon_result.text
        assert GITHUB_CLASSIC_PAT not in anon_result.text

    def test_build_anonymizer_returns_tuple(self):
        """R17.1: build_anonymizer() returns a (AnonymizerEngine, dict) tuple."""
        result = build_anonymizer()
        assert isinstance(result, tuple)
        assert len(result) == 2
        engine, operators = result
        assert isinstance(operators, dict)
