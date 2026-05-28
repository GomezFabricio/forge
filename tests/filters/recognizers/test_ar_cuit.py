"""Tests del recognizer CUIT (REQ-REC-01).

TDD cycle: RED commit imports build_cuit_recognizer which does not exist yet.
"""

import pytest
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry

from forge.filters.recognizers.ar_cuit import build_cuit_recognizer
from tests.filters.fixtures import (
    CUIT_INVALID_CHECKSUM,
    CUIT_RAW_NO_FORMAT,
    CUIT_VALID_1,
    CUIT_VALID_2,
)


def _engine_with_cuit():
    """Return a minimal AnalyzerEngine with only the CUIT recognizer."""
    registry = RecognizerRegistry()
    registry.add_recognizer(build_cuit_recognizer())
    return AnalyzerEngine(registry=registry, nlp_engine=None, supported_languages=["en"])


class TestCuitRecognizer:
    """Unit tests for build_cuit_recognizer() — REQ-REC-01."""

    def test_cuit_detects_valid_formatted(self):
        """R01-A: formatted CUIT with valid mod-11 check digit is detected."""
        engine = _engine_with_cuit()
        results = engine.analyze(
            text=f"El CUIT del proveedor es {CUIT_VALID_1}",
            language="en",
        )
        cuit_results = [r for r in results if r.entity_type == "CUIT"]
        assert len(cuit_results) >= 1
        assert cuit_results[0].score >= 0.85

    def test_cuit_context_boost(self):
        """R01-B: context words 'cuit' and 'proveedor' boost score to >= 1.0."""
        engine = _engine_with_cuit()
        results = engine.analyze(
            text=f"razón social vinculada al cuit {CUIT_VALID_1} del proveedor",
            language="en",
        )
        cuit_results = [r for r in results if r.entity_type == "CUIT"]
        assert len(cuit_results) >= 1
        assert cuit_results[0].score >= 1.0

    def test_cuit_invalid_checksum_rejected(self):
        """R01-C: CUIT with invalid mod-11 check digit is NOT detected."""
        engine = _engine_with_cuit()
        results = engine.analyze(
            text=f"Un CUIT inventado {CUIT_INVALID_CHECKSUM} sin sentido",
            language="en",
        )
        cuit_results = [r for r in results if r.entity_type == "CUIT"]
        assert len(cuit_results) == 0

    def test_cuit_raw_digits_ignored(self):
        """R01-D: raw 12-digit string without XX-XXXXXXXX-X format is ignored."""
        engine = _engine_with_cuit()
        results = engine.analyze(
            text=f"El código de transacción es {CUIT_RAW_NO_FORMAT} interno",
            language="en",
        )
        cuit_results = [r for r in results if r.entity_type == "CUIT"]
        assert len(cuit_results) == 0

    def test_cuit_entity_type_label(self):
        """R01.5: recognizer exposes entity type label CUIT."""
        recognizer = build_cuit_recognizer()
        assert recognizer.supported_entities == ["CUIT"]

    def test_second_valid_cuit_detected(self):
        """Triangulate: second valid CUIT fixture is also detected."""
        engine = _engine_with_cuit()
        results = engine.analyze(
            text=f"CUIT {CUIT_VALID_2} del proveedor",
            language="en",
        )
        cuit_results = [r for r in results if r.entity_type == "CUIT"]
        assert len(cuit_results) >= 1

    @pytest.mark.parametrize("score_context", [
        "cuit",
        "proveedor",
        "contribuyente",
        "afip",
    ])
    def test_cuit_context_words_boost(self, score_context):
        """R01.3: individual context words each trigger boost."""
        engine = _engine_with_cuit()
        text = f"{score_context} {CUIT_VALID_1}"
        results = engine.analyze(text=text, language="en")
        cuit_results = [r for r in results if r.entity_type == "CUIT"]
        assert len(cuit_results) >= 1
        assert cuit_results[0].score >= 1.0
