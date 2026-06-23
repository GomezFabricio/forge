"""Tests for create_guardrails_template() in forge.bootstrap."""
from pathlib import Path


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

    def test_run_includes_guardrails_template(self, tmp_path, monkeypatch):
        """run() should include guardrails_template in report.

        init_codegraph is mocked so the test does not require a 'codegraph'
        binary on PATH. The test targets the guardrails-template deposit, not
        CodeGraph initialisation.
        """
        import forge.bootstrap as _bootstrap
        monkeypatch.setattr(_bootstrap, "init_codegraph", lambda root: (None, "mocked"))
        report = _bootstrap.run(tmp_path)
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
        """GUARDRAILS_TEMPLATE runtime value must equal the content of templates/guardrails.yaml.

        This compares the Python string value of GUARDRAILS_TEMPLATE (as evaluated
        at import time) against the text read from the file at test runtime.
        It does NOT compare raw source bytes — escape sequences in the source are
        already resolved by Python before the comparison runs.
        If this fails, one of the two sources was edited without updating the other."""
        from forge.bootstrap import GUARDRAILS_TEMPLATE
        template_file = Path(__file__).resolve().parent.parent / "templates" / "guardrails.yaml"
        file_content = template_file.read_text(encoding="utf-8")
        assert file_content == GUARDRAILS_TEMPLATE, (
            "GUARDRAILS_TEMPLATE in forge/bootstrap.py has drifted from "
            "templates/guardrails.yaml — update both together"
        )
