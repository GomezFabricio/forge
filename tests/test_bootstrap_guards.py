"""Tests for create_guardrails_template() in forge.bootstrap."""
from pathlib import Path
import pytest


class TestCreateGuardrailsTemplate:
    def test_creates_file_when_missing(self, tmp_path):
        from forge.bootstrap import create_guardrails_template
        result = create_guardrails_template(tmp_path)
        assert result == "created"
        assert (tmp_path / "docs" / "auditoria" / "guardrails.yaml").exists()

    def test_preserves_existing_file(self, tmp_path):
        from forge.bootstrap import create_guardrails_template
        dest = tmp_path / "docs" / "auditoria" / "guardrails.yaml"
        dest.parent.mkdir(parents=True)
        dest.write_text("custom content", encoding="utf-8")
        result = create_guardrails_template(tmp_path)
        assert result == "preserved"
        assert dest.read_text(encoding="utf-8") == "custom content"

    def test_created_file_is_valid_yaml(self, tmp_path):
        import yaml
        from forge.bootstrap import create_guardrails_template
        create_guardrails_template(tmp_path)
        dest = tmp_path / "docs" / "auditoria" / "guardrails.yaml"
        content = yaml.safe_load(dest.read_text(encoding="utf-8"))
        assert isinstance(content, dict)
        assert content.get("version") == 1
        assert isinstance(content.get("rules"), list)

    def test_run_includes_guardrails_template(self, tmp_path):
        """run() should include guardrails_template in report."""
        from forge.bootstrap import run
        report = run(tmp_path)
        assert "guardrails_template" in report
        assert report["guardrails_template"] in ("created", "preserved")

    def test_created_file_has_rules(self, tmp_path):
        """The created file should have at least one rule."""
        import yaml
        from forge.bootstrap import create_guardrails_template
        create_guardrails_template(tmp_path)
        dest = tmp_path / "docs" / "auditoria" / "guardrails.yaml"
        content = yaml.safe_load(dest.read_text(encoding="utf-8"))
        assert len(content.get("rules", [])) > 0

    def test_idempotent_second_call_returns_preserved(self, tmp_path):
        """Calling create_guardrails_template twice preserves the first result."""
        from forge.bootstrap import create_guardrails_template
        result1 = create_guardrails_template(tmp_path)
        assert result1 == "created"
        result2 = create_guardrails_template(tmp_path)
        assert result2 == "preserved"

    def test_inline_template_matches_templates_file(self):
        """GUARDRAILS_TEMPLATE (deployed by bootstrap) must stay byte-identical to
        templates/guardrails.yaml (covered by the anti-R7 and false-positive tests).
        If this fails, one of the two sources was edited without the other."""
        from forge.bootstrap import GUARDRAILS_TEMPLATE
        template_file = Path(__file__).resolve().parent.parent / "templates" / "guardrails.yaml"
        file_content = template_file.read_text(encoding="utf-8")
        assert GUARDRAILS_TEMPLATE == file_content, (
            "GUARDRAILS_TEMPLATE in forge/bootstrap.py has drifted from "
            "templates/guardrails.yaml — update both together"
        )
