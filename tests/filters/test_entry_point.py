"""E2E tests for forge.filters.hook_user_prompt as a subprocess (REQ-HOK-01).

Invokes the module as ``python -m forge.filters.hook_user_prompt`` with JSON
on stdin and asserts stdout + stderr + exit code.

Marked slow because each invocation pays Presidio cold start (~200-300ms).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.filters.fixtures import CUIT_VALID_1

_MODULE = "forge.filters.hook_user_prompt"
_REPO_ROOT = str(Path(__file__).parent.parent.parent)  # .../forge/


def _run(payload: dict):
    """Run the hook as a subprocess, return (stdout_dict, stderr_str, exit_code).

    The subprocess runs from the repo root so that ``forge`` is importable.
    """
    stdin_bytes = json.dumps(payload).encode("utf-8")
    result = subprocess.run(
        [sys.executable, "-m", _MODULE],
        input=stdin_bytes,
        capture_output=True,
        cwd=_REPO_ROOT,
    )
    try:
        stdout_data = json.loads(result.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        stdout_data = result.stdout.decode("utf-8")
    stderr_str = result.stderr.decode("utf-8")
    return stdout_data, stderr_str, result.returncode


@pytest.mark.slow
class TestEntryPoint:
    """E2E tests via subprocess.run."""

    def test_stdin_no_pii_stdout_empty(self):
        """HOK-01-A: prompt with no PII → stdout {}, stderr empty, exit 0."""
        stdout, stderr, code = _run(
            {"prompt": "What is the difference between List and Tuple in Python?"},
        )
        assert code == 0
        assert stdout == {}
        assert "[fg-pii]" not in stderr

    def test_stdin_cuit_stdout_redacted_stderr_note(self):
        """HOK-01-B: prompt with CUIT → stdout modified_prompt, stderr note."""
        stdout, stderr, code = _run(
            {"prompt": f"El CUIT del proveedor es {CUIT_VALID_1}"},
        )
        assert code == 0
        assert stdout.get("continue") is True
        assert "[CUIT]" in stdout.get("modified_prompt", "")
        assert "dato(s) redactado(s)" in stderr
        assert "CUIT" in stderr

    def test_stdin_invalid_json_exit_0_stdout_error(self):
        """HOK-01-C fail-open: invalid JSON → exit 0, stdout contains error key."""
        stdin_bytes = b"not valid json {"
        result = subprocess.run(
            [sys.executable, "-m", _MODULE],
            input=stdin_bytes,
            capture_output=True,
            cwd=_REPO_ROOT,
        )
        assert result.returncode == 0
        stdout_str = result.stdout.decode("utf-8")
        stdout_data = json.loads(stdout_str)
        assert "error" in stdout_data

    def test_fg_pass_passthrough_stderr(self):
        """OVR-01-A e2e: #fg-pass in prompt → stdout {}, stderr passthrough note."""
        stdout, stderr, code = _run(
            {"prompt": f"Test fixture: {CUIT_VALID_1} #fg-pass"},
        )
        assert code == 0
        assert stdout == {}
        assert "passthrough activo" in stderr
