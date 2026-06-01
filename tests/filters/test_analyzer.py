"""Tests del analyzer factory (REQ-ANA-01).

TDD cycle: RED — imports build_analyzer which does not exist yet.
"""

from forge.filters.analyzer import build_analyzer
from tests.filters.fixtures import ANTHROPIC_KEY_VALID, CUIT_VALID_1, OPENAI_KEY_VALID

_ALL_22_ENTITY_TYPES = {
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
}


class TestBuildAnalyzer:
    """Tests for build_analyzer() — REQ-ANA-01."""

    def test_all_22_entity_types_registered(self):
        """ANA-01-A: analyzer supports exactly 22 entity types."""
        engine = build_analyzer()
        supported = set(engine.get_supported_entities(language="en"))
        # All 22 required types must be present
        missing = _ALL_22_ENTITY_TYPES - supported
        assert missing == set(), f"Missing entity types: {missing}"

    def test_no_spacy_required(self):
        """ANA-01-B: build_analyzer() does not require spaCy or NLP models."""
        # If this test runs without spaCy installed, it passes.
        # The mere act of calling build_analyzer() is the test.
        engine = build_analyzer()
        # Also verify a CUIT can be analyzed (basic sanity)
        results = engine.analyze(
            text=f"CUIT del proveedor: {CUIT_VALID_1}",
            language="en",
        )
        cuit_results = [r for r in results if r.entity_type == "CUIT"]
        assert len(cuit_results) >= 1

    def test_anthropic_wins_over_openai(self):
        """ANA-01-C: ANTHROPIC_KEY at score 1.0 wins over OPENAI_KEY for sk-ant- strings."""
        engine = build_analyzer()
        results = engine.analyze(text=ANTHROPIC_KEY_VALID, language="en")
        anthropic_results = [r for r in results if r.entity_type == "ANTHROPIC_KEY"]
        openai_results = [r for r in results if r.entity_type == "OPENAI_KEY"]
        assert len(anthropic_results) >= 1
        assert anthropic_results[0].score == 1.0
        # No OPENAI_KEY should claim the same span
        for oai in openai_results:
            for ant in anthropic_results:
                spans_overlap = not (oai.end <= ant.start or oai.start >= ant.end)
                assert not spans_overlap, (
                    f"OPENAI_KEY ({oai.start}-{oai.end}) overlaps with "
                    f"ANTHROPIC_KEY ({ant.start}-{ant.end})"
                )

    def test_build_analyzer_is_callable_multiple_times(self):
        """R16.6: build_analyzer() is a pure factory — calling it twice yields independent engines."""
        engine1 = build_analyzer()
        engine2 = build_analyzer()
        # Both engines should return consistent results
        results1 = engine1.analyze(text=f"cuit {CUIT_VALID_1}", language="en")
        results2 = engine2.analyze(text=f"cuit {CUIT_VALID_1}", language="en")
        assert len([r for r in results1 if r.entity_type == "CUIT"]) == len(
            [r for r in results2 if r.entity_type == "CUIT"]
        )

    def test_score_threshold_default(self):
        """R16.5: engine uses score_threshold=0.5 — raw DNI digits without context are not returned."""
        engine = build_analyzer()
        # Raw 8-digit number without context: DNI_AR base score 0.3 < 0.5
        results = engine.analyze(
            text="El id es 32456789",
            language="en",
        )
        dni_results = [r for r in results if r.entity_type == "DNI_AR"]
        assert len(dni_results) == 0

    def test_aws_secret_key_with_context_fires(self):
        """Integration: AWS_SECRET_KEY fires with context in full engine."""
        engine = build_analyzer()
        from tests.filters.fixtures import AWS_SECRET_KEY_EXAMPLE
        results = engine.analyze(
            text=f"AWS_SECRET_ACCESS_KEY={AWS_SECRET_KEY_EXAMPLE}",
            language="en",
        )
        aws_results = [r for r in results if r.entity_type == "AWS_SECRET_KEY"]
        assert len(aws_results) >= 1
        assert aws_results[0].score >= 0.85

    def test_openai_key_with_context_fires(self):
        """Integration: OPENAI_KEY fires with context in full engine."""
        engine = build_analyzer()
        results = engine.analyze(
            text=f"OPENAI_API_KEY={OPENAI_KEY_VALID}",
            language="en",
        )
        openai_results = [r for r in results if r.entity_type == "OPENAI_KEY"]
        assert len(openai_results) >= 1
        assert openai_results[0].score >= 0.85
