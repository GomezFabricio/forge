"""Tests del recognizer CBU (REQ-REC-03).

TDD cycle: RED — imports build_cbu_recognizer which does not exist yet.
"""

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry

from forge.filters.recognizers.ar_cbu import build_cbu_recognizer
from tests.filters.fixtures import CBU_INVALID_CHECKSUM, CBU_TOO_SHORT, CBU_VALID


def _engine_with_cbu():
    """Return a minimal AnalyzerEngine with only the CBU recognizer."""
    registry = RecognizerRegistry()
    registry.add_recognizer(build_cbu_recognizer())
    return AnalyzerEngine(registry=registry, nlp_engine=None, supported_languages=["en"])


class TestCbuRecognizer:
    """Unit tests for build_cbu_recognizer() — REQ-REC-03."""

    def test_cbu_valid_detected(self):
        """R03-A: valid 22-digit CBU with correct checksum is detected."""
        engine = _engine_with_cbu()
        results = engine.analyze(
            text=f"La transferencia se acredita en CBU {CBU_VALID}",
            language="en",
        )
        cbu_results = [r for r in results if r.entity_type == "CBU"]
        assert len(cbu_results) >= 1
        assert cbu_results[0].score >= 0.85

    def test_cbu_invalid_checksum_rejected(self):
        """R03-B: 22-digit number with invalid checksum is NOT detected."""
        engine = _engine_with_cbu()
        results = engine.analyze(
            text=f"CBU {CBU_INVALID_CHECKSUM} no válida",
            language="en",
        )
        cbu_results = [r for r in results if r.entity_type == "CBU"]
        assert len(cbu_results) == 0

    def test_cbu_no_context_still_validated(self):
        """R03-C: valid CBU without context word is still detected."""
        engine = _engine_with_cbu()
        results = engine.analyze(text=CBU_VALID, language="en")
        cbu_results = [r for r in results if r.entity_type == "CBU"]
        assert len(cbu_results) >= 1
        assert cbu_results[0].score >= 0.85

    def test_cbu_wrong_length_not_detected(self):
        """R03-D: 21-digit number is NOT detected as CBU."""
        engine = _engine_with_cbu()
        results = engine.analyze(text=CBU_TOO_SHORT, language="en")
        cbu_results = [r for r in results if r.entity_type == "CBU"]
        assert len(cbu_results) == 0

    def test_cbu_entity_type_label(self):
        """R03.4: recognizer exposes entity type label CBU."""
        recognizer = build_cbu_recognizer()
        assert "CBU" in recognizer.supported_entities

    def test_cbu_23digit_not_detected(self):
        """R03-D variant: 23-digit number is NOT detected as CBU."""
        engine = _engine_with_cbu()
        results = engine.analyze(text="07204614880000564597912", language="en")  # 23 digits
        cbu_results = [r for r in results if r.entity_type == "CBU"]
        assert len(cbu_results) == 0
