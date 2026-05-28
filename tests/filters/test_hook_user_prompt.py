"""Tests del processor del hook UserPromptSubmit (forge.filters.hook_user_prompt).

Phase 1: pass-through skeleton (existing tests — kept)
Phase 4: full pipeline with redaction, #fg-pass override, and logging.
"""

import json

from forge.filters.hook_user_prompt import process_prompt
from tests.filters.fixtures import CUIT_VALID_1

# ---------------------------------------------------------------------------
# Legacy pass-through tests (Phase 1 — must stay green)
# ---------------------------------------------------------------------------

class TestPassThrough:
    """Existing pass-through tests — kept for regression."""

    def test_empty_prompt_returns_empty_decision(self):
        result = process_prompt({"prompt": ""})
        assert result == {}

    def test_prompt_without_known_patterns_returns_empty_decision(self):
        result = process_prompt({"prompt": "explicame este código"})
        assert result == {}


# ---------------------------------------------------------------------------
# Full pipeline tests (Phase 4)
# ---------------------------------------------------------------------------

class TestProcessPromptPipeline:
    """Integration tests for process_prompt() with real analyzer+anonymizer."""

    def test_no_pii_returns_empty(self):
        """HOK-01-A: prompt with no PII returns {} (no decision)."""
        result = process_prompt(
            {"prompt": "¿Cuál es la diferencia entre List y Tuple en Python?"},
        )
        assert result == {}

    def test_cuit_redacted(self, tmp_path):
        """HOK-01-B: prompt with CUIT returns modified_prompt with [CUIT] placeholder."""
        log_path = tmp_path / "redactions.jsonl"
        result = process_prompt(
            {"prompt": f"El CUIT del proveedor es {CUIT_VALID_1}"},
            log_path=log_path,
        )
        assert result.get("continue") is True
        assert "[CUIT]" in result["modified_prompt"]
        assert CUIT_VALID_1 not in result["modified_prompt"]

    def test_malformed_input_does_not_crash(self):
        """HOK-01-C variant: missing 'prompt' key is handled gracefully (fail-open)."""
        result = process_prompt({})
        # Fail-open: no PII detected (empty prompt), return {}
        assert isinstance(result, dict)

    def test_multi_entity_redacted(self, tmp_path):
        """HOK-01-D: multiple entity types are all replaced."""
        log_path = tmp_path / "redactions.jsonl"
        result = process_prompt(
            {"prompt": "Email: user@example.com, token AWS: AKIAIOSFODNN7EXAMPLE"},
            log_path=log_path,
        )
        assert result.get("continue") is True
        modified = result["modified_prompt"]
        assert "[EMAIL_ADDRESS]" in modified
        assert "[AWS_ACCESS_KEY]" in modified

    def test_fg_pass_skips_analysis(self, tmp_path):
        """OVR-01-A: #fg-pass in prompt skips all analysis and returns {}."""
        log_path = tmp_path / "redactions.jsonl"
        result = process_prompt(
            {"prompt": f"Test fixture: {CUIT_VALID_1} #fg-pass"},
            log_path=log_path,
        )
        assert result == {}
        # CUIT is NOT replaced
        # (return {} means pass original prompt unchanged)

    def test_fg_pass_in_comment(self, tmp_path):
        """OVR-01-B: #fg-pass in a code comment also triggers override."""
        log_path = tmp_path / "redactions.jsonl"
        result = process_prompt(
            {"prompt": f"# test data\n# #fg-pass\ncuit = '{CUIT_VALID_1}'"},
            log_path=log_path,
        )
        assert result == {}

    def test_fg_pass_uppercase_no_override(self, tmp_path):
        """OVR-01-C: #FG-PASS (uppercase) does NOT trigger override."""
        log_path = tmp_path / "redactions.jsonl"
        result = process_prompt(
            {"prompt": f"El CUIT es {CUIT_VALID_1} #FG-PASS"},
            log_path=log_path,
        )
        # Since CUIT is present and #fg-pass is NOT detected, redaction happens
        assert result.get("continue") is True
        assert "[CUIT]" in result["modified_prompt"]

    def test_pii_logs_redaction(self, tmp_path):
        """LOG: detecting PII appends a redacted event to the JSONL log."""
        log_path = tmp_path / "redactions.jsonl"
        process_prompt(
            {"prompt": f"CUIT del proveedor: {CUIT_VALID_1}"},
            log_path=log_path,
        )
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "redacted"
        assert "CUIT" in entry["types"]

    def test_passthrough_logs_passthrough(self, tmp_path):
        """LOG: #fg-pass triggers a passthrough event in the log."""
        log_path = tmp_path / "redactions.jsonl"
        process_prompt(
            {"prompt": f"cuit {CUIT_VALID_1} #fg-pass"},
            log_path=log_path,
        )
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "passthrough"

    def test_silent_no_log(self, tmp_path):
        """LOG-01-D: no PII and no #fg-pass produces NO log entry."""
        log_path = tmp_path / "redactions.jsonl"
        process_prompt(
            {"prompt": "una pregunta genérica sin PII"},
            log_path=log_path,
        )
        assert not log_path.exists()

    def test_fg_pass_is_case_sensitive(self, tmp_path):
        """OVR-01 R20.6: only literal #fg-pass triggers override; #fg_pass does not."""
        log_path = tmp_path / "redactions.jsonl"
        result = process_prompt(
            {"prompt": f"cuit {CUIT_VALID_1} #fg_pass"},
            log_path=log_path,
        )
        # #fg_pass (underscore) should NOT trigger override → CUIT is redacted
        assert result.get("continue") is True
        assert "[CUIT]" in result["modified_prompt"]
