"""Tests del hook PreToolUse de guardrails (forge.guards.hook_pre_tool)."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from forge.guards.hook_pre_tool import process_hook, _is_guard_disabled, _hash_command


def _make_payload(command: str, cwd: str, tool_name: str = "Bash") -> dict:
    return {
        "tool_name": tool_name,
        "cwd": cwd,
        "tool_input": {"command": command},
    }


def _write_guardrails(tmp_path: Path, rules: list) -> Path:
    """Write a guardrails.yaml with given rules. Returns guardrails path."""
    guardrails_dir = tmp_path / "docs" / "auditoria"
    guardrails_dir.mkdir(parents=True)
    guardrails_path = guardrails_dir / "guardrails.yaml"
    guardrails_path.write_text(
        yaml.dump({"version": 1, "rules": rules}),
        encoding="utf-8",
    )
    return guardrails_path


class TestInputValidation:
    def test_non_bash_tool_returns_empty(self, tmp_path):
        result = process_hook({"tool_name": "Read", "cwd": str(tmp_path), "tool_input": {"command": "rm -rf /"}})
        assert result == {}

    def test_bash_empty_command_returns_empty(self, tmp_path):
        guardrails_dir = tmp_path / "docs" / "auditoria"
        guardrails_dir.mkdir(parents=True)
        (guardrails_dir / "guardrails.yaml").write_text("version: 1\nrules: []\n")
        result = process_hook({"tool_name": "Bash", "cwd": str(tmp_path), "tool_input": {"command": ""}})
        assert result == {}

    def test_missing_guardrails_returns_empty(self, tmp_path):
        result = process_hook({"tool_name": "Bash", "cwd": str(tmp_path), "tool_input": {"command": "rm -rf /"}})
        assert result == {}

    def test_missing_cwd_returns_empty(self):
        result = process_hook({"tool_name": "Bash", "cwd": "", "tool_input": {"command": "rm -rf /"}})
        assert result == {}

    def test_whitespace_only_command_returns_empty(self, tmp_path):
        guardrails_dir = tmp_path / "docs" / "auditoria"
        guardrails_dir.mkdir(parents=True)
        (guardrails_dir / "guardrails.yaml").write_text("version: 1\nrules: []\n")
        result = process_hook({"tool_name": "Bash", "cwd": str(tmp_path), "tool_input": {"command": "   "}})
        assert result == {}

    def test_tool_input_not_dict_returns_empty(self, tmp_path):
        result = process_hook({"tool_name": "Bash", "cwd": str(tmp_path), "tool_input": "not a dict"})
        assert result == {}


class TestRuleEvaluation:
    def test_block_rule_returns_deny(self, tmp_path):
        log_path = tmp_path / "guard.jsonl"
        _write_guardrails(tmp_path, [
            {"pattern": "rm -rf", "action": "block", "reason": "irrecuperable"}
        ])
        result = process_hook(_make_payload("rm -rf /tmp/test", str(tmp_path)), log_path=log_path)
        assert result != {}
        out = result["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny"
        assert "irrecuperable" in out["permissionDecisionReason"]

    def test_confirm_rule_returns_ask(self, tmp_path):
        log_path = tmp_path / "guard.jsonl"
        _write_guardrails(tmp_path, [
            {"pattern": "git push --force", "action": "confirm", "reason": "peligroso"}
        ])
        result = process_hook(_make_payload("git push --force", str(tmp_path)), log_path=log_path)
        assert result != {}
        out = result["hookSpecificOutput"]
        assert out["permissionDecision"] == "ask"
        assert "peligroso" in out["permissionDecisionReason"]

    def test_no_match_returns_empty(self, tmp_path):
        _write_guardrails(tmp_path, [
            {"pattern": "rm -rf", "action": "block", "reason": "bad"}
        ])
        result = process_hook(_make_payload("git status", str(tmp_path)))
        assert result == {}

    def test_first_match_wins(self, tmp_path):
        log_path = tmp_path / "guard.jsonl"
        _write_guardrails(tmp_path, [
            {"pattern": "dangerous", "action": "block", "reason": "first"},
            {"pattern": "dangerous", "action": "confirm", "reason": "second"},
        ])
        result = process_hook(_make_payload("dangerous command", str(tmp_path)), log_path=log_path)
        out = result["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny"  # block from first rule
        assert "first" in out["permissionDecisionReason"]

    def test_ignorecase_flag(self, tmp_path):
        log_path = tmp_path / "guard.jsonl"
        _write_guardrails(tmp_path, [
            {"pattern": "DROP TABLE", "action": "block", "reason": "sql", "ignorecase": True}
        ])
        result = process_hook(_make_payload("drop table users;", str(tmp_path)), log_path=log_path)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_case_sensitive_by_default(self, tmp_path):
        _write_guardrails(tmp_path, [
            {"pattern": "DROP TABLE", "action": "block", "reason": "sql"}
        ])
        result = process_hook(_make_payload("drop table users;", str(tmp_path)))
        assert result == {}  # no match because case sensitive

    def test_alternative_combined_in_reason(self, tmp_path):
        log_path = tmp_path / "guard.jsonl"
        _write_guardrails(tmp_path, [
            {"pattern": "rm -rf", "action": "block", "reason": "irrecuperable", "alternative": "mover a /tmp"}
        ])
        result = process_hook(_make_payload("rm -rf /old", str(tmp_path)), log_path=log_path)
        reason = result["hookSpecificOutput"]["permissionDecisionReason"]
        assert "Razón:" in reason
        assert "Alternativa:" in reason
        assert "mover a /tmp" in reason

    def test_invalid_rule_skipped_and_logged(self, tmp_path):
        log_path = tmp_path / "guard.jsonl"
        _write_guardrails(tmp_path, [
            {"action": "block", "reason": "missing pattern"},  # invalid: no pattern
            {"pattern": "rm -rf", "action": "block", "reason": "valid"},
        ])
        result = process_hook(_make_payload("rm -rf /tmp", str(tmp_path)), log_path=log_path)
        # Valid rule still works
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        # Error logged for invalid rule
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        actions = [json.loads(line)["action"] for line in lines]
        assert "error" in actions

    def test_yaml_parse_error_returns_empty_and_logs_error(self, tmp_path):
        log_path = tmp_path / "guard.jsonl"
        guardrails_dir = tmp_path / "docs" / "auditoria"
        guardrails_dir.mkdir(parents=True)
        (guardrails_dir / "guardrails.yaml").write_text("{ invalid: yaml: : :", encoding="utf-8")
        result = process_hook(_make_payload("rm -rf /", str(tmp_path)), log_path=log_path)
        assert result == {}
        # Error must be logged
        assert log_path.exists()
        entry = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert entry["action"] == "error"

    def test_empty_rules_list_returns_empty(self, tmp_path):
        _write_guardrails(tmp_path, [])
        result = process_hook(_make_payload("rm -rf /", str(tmp_path)))
        assert result == {}

    def test_invalid_action_skipped_and_logged(self, tmp_path):
        log_path = tmp_path / "guard.jsonl"
        _write_guardrails(tmp_path, [
            {"pattern": "rm -rf", "action": "unknown_action", "reason": "bad action"},
            {"pattern": "rm -rf", "action": "block", "reason": "valid"},
        ])
        result = process_hook(_make_payload("rm -rf /", str(tmp_path)), log_path=log_path)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        actions = [json.loads(line)["action"] for line in lines]
        assert "error" in actions


class TestLogShape:
    def test_log_entry_contains_action_pattern_hash_no_command(self, tmp_path):
        log_path = tmp_path / "guard.jsonl"
        command = "rm -rf /sensitive/data"
        _write_guardrails(tmp_path, [
            {"pattern": "rm -rf", "action": "block", "reason": "bad"}
        ])
        process_hook(_make_payload(command, str(tmp_path)), log_path=log_path)
        entry = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert entry["action"] == "block"
        assert entry["pattern"] == "rm -rf"
        assert "command_hash" in entry
        assert len(entry["command_hash"]) == 16
        # Raw command must NOT be in the log
        assert command not in json.dumps(entry)

    def test_log_entry_command_hash_is_sha256_16hex(self, tmp_path):
        log_path = tmp_path / "guard.jsonl"
        command = "rm -rf /test"
        _write_guardrails(tmp_path, [
            {"pattern": "rm -rf", "action": "block", "reason": "bad"}
        ])
        process_hook(_make_payload(command, str(tmp_path)), log_path=log_path)
        entry = json.loads(log_path.read_text(encoding="utf-8").strip())
        expected_hash = _hash_command(command)
        assert entry["command_hash"] == expected_hash
        assert len(entry["command_hash"]) == 16

    def test_logging_failure_swallowed(self, tmp_path):
        # Make log path inside a file (not a dir) to cause OSError
        blocker = tmp_path / "blocker"
        blocker.write_text("I am a file")
        bad_log = blocker / "guard.jsonl"
        _write_guardrails(tmp_path, [
            {"pattern": "rm -rf", "action": "block", "reason": "bad"}
        ])
        # Must not raise
        result = process_hook(_make_payload("rm -rf /", str(tmp_path)), log_path=bad_log)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_log_has_timestamp(self, tmp_path):
        log_path = tmp_path / "guard.jsonl"
        _write_guardrails(tmp_path, [
            {"pattern": "rm -rf", "action": "block", "reason": "bad"}
        ])
        process_hook(_make_payload("rm -rf /", str(tmp_path)), log_path=log_path)
        entry = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert "ts" in entry
        assert entry["ts"].endswith("Z")


class TestKillSwitch:
    def test_forge_guard_disable_set_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FORGE_GUARD_DISABLE", "1")
        _write_guardrails(tmp_path, [
            {"pattern": "rm -rf", "action": "block", "reason": "bad"}
        ])
        result = process_hook(_make_payload("rm -rf /", str(tmp_path)))
        assert result == {}

    def test_forge_guard_disable_truthy_string_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FORGE_GUARD_DISABLE", "true")
        _write_guardrails(tmp_path, [
            {"pattern": "rm -rf", "action": "block", "reason": "bad"}
        ])
        result = process_hook(_make_payload("rm -rf /", str(tmp_path)))
        assert result == {}

    def test_forge_guard_disable_empty_string_not_disabled(self, monkeypatch):
        monkeypatch.setenv("FORGE_GUARD_DISABLE", "")
        assert not _is_guard_disabled()

    def test_forge_guard_disable_zero_not_disabled(self, monkeypatch):
        monkeypatch.setenv("FORGE_GUARD_DISABLE", "0")
        assert not _is_guard_disabled()

    def test_forge_guard_disable_unset_not_disabled(self, monkeypatch):
        monkeypatch.delenv("FORGE_GUARD_DISABLE", raising=False)
        assert not _is_guard_disabled()


class TestAntiR7Template:
    """Anti-R7: alternatives must not match their own rule's pattern."""

    def test_alternatives_do_not_match_own_pattern(self):
        """For every rule in templates/guardrails.yaml with an alternative,
        assert the alternative does NOT match the rule's own pattern."""
        # Load the actual template file
        repo_root = Path(__file__).resolve().parent.parent.parent
        template_path = repo_root / "templates" / "guardrails.yaml"
        assert template_path.exists(), f"Template not found at {template_path}"

        content = yaml.safe_load(template_path.read_text(encoding="utf-8"))
        rules = content.get("rules", [])

        failures = []
        for rule in rules:
            pattern_str = rule.get("pattern")
            alternative = rule.get("alternative", "")
            action = rule.get("action", "")

            if not pattern_str or not alternative:
                continue

            flags = re.IGNORECASE if rule.get("ignorecase") else 0
            try:
                regex = re.compile(pattern_str, flags)
            except re.error:
                continue  # invalid pattern — other tests will catch

            if regex.search(alternative):
                failures.append(
                    f"Rule '{pattern_str}' ({action}): alternative '{alternative}' "
                    f"matches the rule's own pattern — this would block the suggested remedy!"
                )

        assert not failures, "Anti-R7 failures:\n" + "\n".join(failures)


class TestTemplateFalsePositives:
    """Block rules from the real template must not match innocent commands."""

    @pytest.fixture()
    def template_cwd(self, tmp_path):
        """Deposit the real templates/guardrails.yaml into a tmp project."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        template_path = repo_root / "templates" / "guardrails.yaml"
        guardrails_dir = tmp_path / "docs" / "auditoria"
        guardrails_dir.mkdir(parents=True)
        (guardrails_dir / "guardrails.yaml").write_text(
            template_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        return tmp_path

    def test_git_rm_cached_is_not_blocked(self, template_cwd):
        """git rm -rf --cached only untracks files (non-destructive) — must pass."""
        result = process_hook(_make_payload("git rm -rf --cached src/", str(template_cwd)))
        assert result == {}

    def test_plain_rm_rf_is_blocked(self, template_cwd):
        result = process_hook(_make_payload("rm -rf build/", str(template_cwd)))
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_chained_rm_rf_is_blocked(self, template_cwd):
        result = process_hook(_make_payload("cd /tmp && rm -rf cache", str(template_cwd)))
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_sudo_rm_rf_is_blocked(self, template_cwd):
        result = process_hook(_make_payload("sudo rm -rf /var/log/app", str(template_cwd)))
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.slow
class TestE2ESubprocess:
    def test_e2e_block_rule(self, tmp_path):
        """E2E: piping a payload to python -m forge.guards.hook_pre_tool returns deny JSON."""
        guardrails_dir = tmp_path / "docs" / "auditoria"
        guardrails_dir.mkdir(parents=True)
        (guardrails_dir / "guardrails.yaml").write_text(
            "version: 1\nrules:\n  - pattern: 'rm -rf'\n    action: block\n    reason: 'irrecuperable'\n",
            encoding="utf-8",
        )
        payload = json.dumps({
            "tool_name": "Bash",
            "cwd": str(tmp_path),
            "tool_input": {"command": "rm -rf /tmp/testdir"},
        })
        result = subprocess.run(
            [sys.executable, "-m", "forge.guards.hook_pre_tool"],
            input=payload,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_e2e_no_guardrails_returns_empty(self, tmp_path):
        """E2E: no guardrails.yaml -> empty JSON {}."""
        payload = json.dumps({
            "tool_name": "Bash",
            "cwd": str(tmp_path),
            "tool_input": {"command": "rm -rf /tmp/test"},
        })
        result = subprocess.run(
            [sys.executable, "-m", "forge.guards.hook_pre_tool"],
            input=payload,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert json.loads(result.stdout) == {}

    def test_e2e_malformed_json_returns_empty(self):
        """E2E: malformed JSON on stdin -> {} and exit 0 (fail-open)."""
        result = subprocess.run(
            [sys.executable, "-m", "forge.guards.hook_pre_tool"],
            input="not json at all",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert json.loads(result.stdout) == {}

    def test_e2e_confirm_rule_returns_ask(self, tmp_path):
        """E2E: confirm rule -> ask JSON."""
        guardrails_dir = tmp_path / "docs" / "auditoria"
        guardrails_dir.mkdir(parents=True)
        (guardrails_dir / "guardrails.yaml").write_text(
            "version: 1\nrules:\n  - pattern: 'git push'\n    action: confirm\n    reason: 'reescribe historia'\n",
            encoding="utf-8",
        )
        payload = json.dumps({
            "tool_name": "Bash",
            "cwd": str(tmp_path),
            "tool_input": {"command": "git push --force origin main"},
        })
        result = subprocess.run(
            [sys.executable, "-m", "forge.guards.hook_pre_tool"],
            input=payload,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["hookSpecificOutput"]["permissionDecision"] == "ask"
