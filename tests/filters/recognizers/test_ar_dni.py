"""Tests del recognizer DNI_AR (REQ-REC-02).

TDD cycle: RED — imports build_dni_recognizer which does not exist yet.
"""

import pytest
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry

from forge.filters.recognizers.ar_dni import build_dni_recognizer


def _engine_with_dni():
    """Return a minimal AnalyzerEngine with only the DNI_AR recognizer."""
    registry = RecognizerRegistry()
    registry.add_recognizer(build_dni_recognizer())
    return AnalyzerEngine(registry=registry, nlp_engine=None, supported_languages=["en"])


class TestDniRecognizer:
    """Unit tests for build_dni_recognizer() — REQ-REC-02."""

    def test_dni_formatted_detected(self):
        """R02-A: formatted DNI with dots is detected with score >= 0.7."""
        engine = _engine_with_dni()
        results = engine.analyze(text="Mi DNI es 32.456.789", language="en")
        dni_results = [r for r in results if r.entity_type == "DNI_AR"]
        assert len(dni_results) >= 1
        assert dni_results[0].score >= 0.7

    def test_dni_raw_with_context_detected(self):
        """R02-B: raw 8-digit DNI with context word is detected with score >= 0.5."""
        engine = _engine_with_dni()
        results = engine.analyze(
            text="El número de documento del titular es 32456789",
            language="en",
        )
        dni_results = [r for r in results if r.entity_type == "DNI_AR"]
        assert len(dni_results) >= 1
        assert dni_results[0].score >= 0.5

    def test_dni_raw_without_context_not_detected(self):
        """R02-C: raw 8-digit number without context is NOT detected at threshold 0.5."""
        engine = _engine_with_dni()
        # engine uses score_threshold=0.5 by default
        results = engine.analyze(
            text="El id de la transacción es 32456789",
            language="en",
            score_threshold=0.5,
        )
        dni_results = [r for r in results if r.entity_type == "DNI_AR"]
        assert len(dni_results) == 0

    def test_dni_timestamp_pool_not_detected(self):
        """R02-D: 7-8 digit numbers resembling timestamps without context are NOT detected."""
        engine = _engine_with_dni()
        non_dni_numbers = [
            "12345678",
            "20240101",
            "00000001",
            "99999999",
            "1234567",
            "9876543",
        ]
        for number in non_dni_numbers:
            results = engine.analyze(
                text=number,
                language="en",
                score_threshold=0.5,
            )
            dni_results = [r for r in results if r.entity_type == "DNI_AR"]
            assert len(dni_results) == 0, f"False positive on: {number}"

    def test_dni_entity_type_label(self):
        """R02.5: recognizer exposes entity type label DNI_AR."""
        recognizer = build_dni_recognizer()
        assert "DNI_AR" in recognizer.supported_entities

    def test_dni_7digit_with_context_detected(self):
        """R02-B variant: 7-digit DNI with context word is also detected."""
        engine = _engine_with_dni()
        results = engine.analyze(
            text="dni 7654321 del titular",
            language="en",
            score_threshold=0.5,
        )
        dni_results = [r for r in results if r.entity_type == "DNI_AR"]
        assert len(dni_results) >= 1
        assert dni_results[0].score >= 0.5

    @pytest.mark.parametrize("context_word", ["dni", "documento", "doc", "nro"])
    def test_dni_context_words_boost_raw(self, context_word):
        """R02.4: each context word boosts raw-digits score to >= 0.5."""
        engine = _engine_with_dni()
        text = f"{context_word} 32456789"
        results = engine.analyze(text=text, language="en", score_threshold=0.5)
        dni_results = [r for r in results if r.entity_type == "DNI_AR"]
        assert len(dni_results) >= 1
        assert dni_results[0].score >= 0.5
