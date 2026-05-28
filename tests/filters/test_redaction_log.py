"""Tests del redaction logger (REQ-LOG-01).

TDD cycle: RED — imports from redaction_log which does not exist yet.
"""

import json
from pathlib import Path

import pytest

from forge.filters.redaction_log import hash_prompt, log_event


class TestHashPrompt:
    """Tests for hash_prompt() helper."""

    def test_returns_16_hex_chars(self):
        """R21.2: prompt_hash is a 16-character hex string (SHA-256[:16])."""
        h = hash_prompt("hello world")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_input_same_hash(self):
        """hash_prompt is deterministic."""
        h1 = hash_prompt("Mi CUIT es 20-12345678-6")
        h2 = hash_prompt("Mi CUIT es 20-12345678-6")
        assert h1 == h2

    def test_different_input_different_hash(self):
        """Different inputs produce different hashes (no collisions in simple cases)."""
        h1 = hash_prompt("hello")
        h2 = hash_prompt("world")
        assert h1 != h2

    def test_hash_does_not_contain_prompt_content(self):
        """R21.5: the hash value does not contain the original prompt text."""
        prompt = "secretpassword"
        h = hash_prompt(prompt)
        assert prompt not in h


class TestLogEvent:
    """Tests for log_event() helper — REQ-LOG-01."""

    def test_log_event_redacted_appends_jsonl(self, tmp_path):
        """LOG-01-A: redaction event is appended as valid JSONL."""
        log_path = tmp_path / "redactions.jsonl"
        log_event(
            action="redacted",
            types={"CUIT": 2, "EMAIL_ADDRESS": 1},
            prompt_hash="a3f9b21c8d4e0f12",
            log_path=log_path,
        )
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "redacted"
        assert entry["types"] == {"CUIT": 2, "EMAIL_ADDRESS": 1}
        assert entry["count"] == 3  # 2 + 1
        assert entry["prompt_hash"] == "a3f9b21c8d4e0f12"
        assert "ts" in entry
        assert entry["ts"].endswith("Z")

    def test_log_event_passthrough(self, tmp_path):
        """LOG-01-B: passthrough event is logged with empty types and count=0."""
        log_path = tmp_path / "redactions.jsonl"
        log_event(
            action="passthrough",
            types={},
            prompt_hash="deadbeef00000001",
            log_path=log_path,
        )
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["action"] == "passthrough"
        assert entry["types"] == {}
        assert entry["count"] == 0

    def test_multiple_appends_no_overwrite(self, tmp_path):
        """LOG-01-C: multiple log_event calls append — do not overwrite."""
        log_path = tmp_path / "redactions.jsonl"
        for i in range(3):
            log_event(
                action="redacted",
                types={"CUIT": 1},
                prompt_hash=f"hash{i:012x}",
                log_path=log_path,
            )
        # Now append a 4th
        log_event(
            action="passthrough",
            types={},
            prompt_hash="new0000000000001",
            log_path=log_path,
        )
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 4
        # First 3 are unchanged (redacted)
        for i, line in enumerate(lines[:3]):
            entry = json.loads(line)
            assert entry["action"] == "redacted"
        # 4th is passthrough
        assert json.loads(lines[3])["action"] == "passthrough"

    def test_forge_dir_created_if_missing(self, tmp_path):
        """R21.4: .forge/ directory is created if it does not exist."""
        log_path = tmp_path / ".forge" / "redactions.jsonl"
        assert not (tmp_path / ".forge").exists()
        log_event(
            action="redacted",
            types={"JWT": 1},
            prompt_hash="abc123def456abcd",
            log_path=log_path,
        )
        assert log_path.exists()

    def test_log_does_not_contain_prompt_text(self, tmp_path):
        """R21.5: log entry does NOT contain prompt text — only hash."""
        log_path = tmp_path / "redactions.jsonl"
        log_event(
            action="redacted",
            types={"CUIT": 1},
            prompt_hash="a3f9b21c8d4e0f12",
            log_path=log_path,
        )
        raw = log_path.read_text(encoding="utf-8")
        # The actual hash value is fine, but no prompt text should appear
        # (this test verifies no additional fields were added)
        entry = json.loads(raw.strip())
        assert "prompt" not in entry
        assert "text" not in entry
        assert "modified_prompt" not in entry

    def test_lf_line_endings(self, tmp_path):
        """R21 Windows: log file uses LF line endings (no CRLF)."""
        log_path = tmp_path / "redactions.jsonl"
        log_event(
            action="redacted",
            types={"CUIT": 1},
            prompt_hash="aabbccddeeff0011",
            log_path=log_path,
        )
        raw_bytes = log_path.read_bytes()
        assert b"\r\n" not in raw_bytes, "CRLF found in log file (expected LF only)"
