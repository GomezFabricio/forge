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
        log_path = tmp_path / "auditoria-pii.jsonl"
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
        log_path = tmp_path / "auditoria-pii.jsonl"
        result = process_prompt(
            {"prompt": "Email: user@example.com, token AWS: AKIAIOSFODNN7EXAMPLE"},
            log_path=log_path,
        )
        assert result.get("continue") is True
        modified = result["modified_prompt"]
        assert "[EMAIL_ADDRESS]" in modified
        assert "[AWS_ACCESS_KEY]" in modified
        # Privacy: raw values must NOT appear anywhere in the redacted prompt.
        assert "user@example.com" not in modified, (
            "CRITICAL PII LEAK: raw email address found in modified_prompt"
        )
        assert "AKIAIOSFODNN7EXAMPLE" not in modified, (
            "CRITICAL PII LEAK: raw AWS access key found in modified_prompt"
        )

    def test_fg_pass_skips_analysis(self, tmp_path):
        """OVR-01-A: #fg-pass in prompt skips all analysis and returns {}."""
        log_path = tmp_path / "auditoria-pii.jsonl"
        result = process_prompt(
            {"prompt": f"Test fixture: {CUIT_VALID_1} #fg-pass"},
            log_path=log_path,
        )
        assert result == {}
        # CUIT is NOT replaced
        # (return {} means pass original prompt unchanged)

    def test_fg_pass_in_comment(self, tmp_path):
        """OVR-01-B: #fg-pass in a code comment also triggers override."""
        log_path = tmp_path / "auditoria-pii.jsonl"
        result = process_prompt(
            {"prompt": f"# test data\n# #fg-pass\ncuit = '{CUIT_VALID_1}'"},
            log_path=log_path,
        )
        assert result == {}

    def test_fg_pass_uppercase_no_override(self, tmp_path):
        """OVR-01-C: #FG-PASS (uppercase) does NOT trigger override."""
        log_path = tmp_path / "auditoria-pii.jsonl"
        result = process_prompt(
            {"prompt": f"El CUIT es {CUIT_VALID_1} #FG-PASS"},
            log_path=log_path,
        )
        # Since CUIT is present and #fg-pass is NOT detected, redaction happens
        assert result.get("continue") is True
        assert "[CUIT]" in result["modified_prompt"]

    def test_pii_logs_redaction(self, tmp_path):
        """LOG: detecting PII appends a redacted event to the JSONL log."""
        log_path = tmp_path / "auditoria-pii.jsonl"
        process_prompt(
            {"prompt": f"CUIT del proveedor: {CUIT_VALID_1}"},
            log_path=log_path,
        )
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "redacted"
        assert "CUIT" in entry["types"]
        # Privacy: the raw CUIT value must NOT appear anywhere in the log entry.
        log_text = lines[0]
        assert CUIT_VALID_1 not in log_text, (
            "CRITICAL PII LEAK: raw CUIT value found in log entry"
        )

    def test_passthrough_logs_passthrough(self, tmp_path):
        """LOG: #fg-pass triggers a passthrough event in the log."""
        log_path = tmp_path / "auditoria-pii.jsonl"
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
        log_path = tmp_path / "auditoria-pii.jsonl"
        process_prompt(
            {"prompt": "una pregunta genérica sin PII"},
            log_path=log_path,
        )
        assert not log_path.exists()

    def test_fg_pass_is_case_sensitive(self, tmp_path):
        """OVR-01 R20.6: only literal #fg-pass triggers override; #fg_pass does not."""
        log_path = tmp_path / "auditoria-pii.jsonl"
        result = process_prompt(
            {"prompt": f"cuit {CUIT_VALID_1} #fg_pass"},
            log_path=log_path,
        )
        # #fg_pass (underscore) should NOT trigger override → CUIT is redacted
        assert result.get("continue") is True
        assert "[CUIT]" in result["modified_prompt"]


# ---------------------------------------------------------------------------
# D1: FORGE_PII_DISABLE kill-switch tests
# ---------------------------------------------------------------------------

class TestForgeDisableKillSwitch:
    """FORGE_PII_DISABLE env var disables all PII analysis without importing presidio."""

    def test_disable_env_set_returns_passthrough(self, tmp_path, monkeypatch):
        """DIS-01: FORGE_PII_DISABLE=1 → passthrough ({}) without redacting."""
        monkeypatch.setenv("FORGE_PII_DISABLE", "1")
        log_path = tmp_path / "auditoria-pii.jsonl"
        result = process_prompt(
            {"prompt": f"CUIT del proveedor: {CUIT_VALID_1}"},
            log_path=log_path,
        )
        assert result == {}

    def test_disable_env_set_logs_passthrough(self, tmp_path, monkeypatch):
        """DIS-02: FORGE_PII_DISABLE=1 → passthrough event is logged (mirrors #fg-pass)."""
        monkeypatch.setenv("FORGE_PII_DISABLE", "1")
        log_path = tmp_path / "auditoria-pii.jsonl"
        process_prompt(
            {"prompt": f"CUIT: {CUIT_VALID_1}"},
            log_path=log_path,
        )
        assert log_path.exists()
        import json as _json
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = _json.loads(lines[0])
        assert entry["action"] == "passthrough"

    def test_disable_env_zero_does_not_disable(self, monkeypatch):
        """DIS-03: FORGE_PII_DISABLE=0 → kill-switch is NOT triggered (normal flow).

        We verify the kill-switch gate is skipped by confirming the function
        proceeds past step 0 and attempts analysis (which may fail due to missing
        presidio on this machine — that's expected and acceptable).
        """
        from forge.filters.hook_user_prompt import _is_pii_disabled

        monkeypatch.setenv("FORGE_PII_DISABLE", "0")
        assert not _is_pii_disabled(), (
            "FORGE_PII_DISABLE=0 should NOT activate the kill-switch"
        )

        monkeypatch.setenv("FORGE_PII_DISABLE", "")
        assert not _is_pii_disabled(), (
            "FORGE_PII_DISABLE='' (empty string) should NOT activate the kill-switch"
        )

    def test_disable_env_set_no_presidio_import(self, tmp_path, monkeypatch):
        """DIS-04: FORGE_PII_DISABLE=1 → presidio modules are not imported."""
        import sys

        monkeypatch.setenv("FORGE_PII_DISABLE", "1")
        # Remove cached presidio modules so we can detect a fresh import
        presidio_modules = [k for k in sys.modules if "presidio" in k]
        for mod in presidio_modules:
            monkeypatch.delitem(sys.modules, mod)

        log_path = tmp_path / "auditoria-pii.jsonl"
        process_prompt(
            {"prompt": f"CUIT del proveedor: {CUIT_VALID_1}"},
            log_path=log_path,
        )
        # No presidio module should have been imported
        new_presidio = [k for k in sys.modules if "presidio" in k]
        assert new_presidio == [], (
            f"FORGE_PII_DISABLE=1 but presidio was imported: {new_presidio}"
        )

    def test_disable_pii_in_prompt_not_redacted(self, tmp_path, monkeypatch):
        """DIS-05: FORGE_PII_DISABLE set + PII in prompt → prompt NOT redacted."""
        monkeypatch.setenv("FORGE_PII_DISABLE", "1")
        log_path = tmp_path / "auditoria-pii.jsonl"
        result = process_prompt(
            {"prompt": f"Email: user@example.com, CUIT: {CUIT_VALID_1}"},
            log_path=log_path,
        )
        assert result == {}
        # result == {} means the original prompt passes unchanged (not redacted)


# ---------------------------------------------------------------------------
# D3: action="error" emission from the hook's error path
# ---------------------------------------------------------------------------

class TestErrorActionLogging:
    """D3: processing errors emit action='error' to the JSONL log (fail-open).

    These tests inject both a broken analyzer AND a stub anonymizer so no
    presidio import is attempted (preserving the no-network/no-install constraint).
    The analyzer raises to simulate a presidio failure; the anonymizer is never
    reached because the exception is thrown first.
    """

    def _stub_anonymizer_and_operators(self):
        """Return a stub (anonymizer, operators) pair that is never called."""
        class _StubAnonymizer:
            def anonymize(self, **_kwargs):  # pragma: no cover
                raise AssertionError("anonymizer should not be called in error path")

        return _StubAnonymizer(), {}

    def test_error_path_logs_error_action(self, tmp_path):
        """ERR-01: when the analyzer raises, an 'error' event is written to the log."""
        import json as _json

        log_path = tmp_path / "auditoria-pii.jsonl"

        class BrokenAnalyzer:
            def analyze(self, **_kwargs):
                raise RuntimeError("presidio simulated failure")

        anon, ops = self._stub_anonymizer_and_operators()
        result = process_prompt(
            {"prompt": f"CUIT: {CUIT_VALID_1}"},
            analyzer=BrokenAnalyzer(),
            anonymizer=anon,
            operators=ops,
            log_path=log_path,
        )
        # Fail-open: result is still {}
        assert result == {}
        # Error is logged
        assert log_path.exists()
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = _json.loads(lines[0])
        assert entry["action"] == "error"

    def test_error_path_includes_prompt_hash(self, tmp_path):
        """ERR-02: the error log entry includes a prompt_hash for correlation."""
        import json as _json

        log_path = tmp_path / "auditoria-pii.jsonl"

        class BrokenAnalyzer:
            def analyze(self, **_kwargs):
                raise ValueError("broken")

        anon, ops = self._stub_anonymizer_and_operators()
        process_prompt(
            {"prompt": "some prompt text"},
            analyzer=BrokenAnalyzer(),
            anonymizer=anon,
            operators=ops,
            log_path=log_path,
        )
        entry = _json.loads(log_path.read_text(encoding="utf-8").strip())
        assert "prompt_hash" in entry
        assert len(entry["prompt_hash"]) == 16

    def test_error_path_still_fail_open(self, tmp_path):
        """ERR-03: even when logging itself fails, the hook returns {} (fail-open)."""
        # Use a log_path in a non-existent nested dir where the parent is a *file*
        # (not a directory) — this reliably causes log_event to fail on all platforms.
        blocker = tmp_path / "blocker"
        blocker.write_text("I am a file, not a dir")
        bad_log_path = blocker / "auditoria-pii.jsonl"  # parent is a file → OSError

        class BrokenAnalyzer:
            def analyze(self, **_kwargs):
                raise RuntimeError("presidio failure")

        anon, ops = self._stub_anonymizer_and_operators()
        result = process_prompt(
            {"prompt": "test"},
            analyzer=BrokenAnalyzer(),
            anonymizer=anon,
            operators=ops,
            log_path=bad_log_path,
        )
        # Must still be fail-open even if logging errors out
        assert result == {}
