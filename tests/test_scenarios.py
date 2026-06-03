"""End-to-end scenario tests for the 4 forge use cases defined in PRD
`.forge/prd-activacion-latente.md` Section 3.2.

These tests verify that the bootstrap helper chain composes correctly for each
scenario's user journey. They do NOT test LLM/skill-level behavior (vision
conversation prose, fg-plan --from flag parsing, etc.) — that surface is
verified manually via sdd-verify. They DO verify that all Python-testable
helpers produce the correct filesystem and config state for each scenario.

Covers DoD #12: "Tests cubren los 4 escenarios end-to-end (al menos un test
por escenario)."
"""

from pathlib import Path

import yaml

from forge.bootstrap import (
    create_arquitectura_docs,
    create_audit_config,
    detect_mode,
    is_legacy_project,
    is_vision_skipped,
    mark_vision_skipped,
    patch_config_stacks,
    read_overview,
)

# ---------------------------------------------------------------------------
# Scenario 1: Greenfield — no pre-existing docs
# ---------------------------------------------------------------------------


class TestScenario1GreenfieldNoDocs:
    """Scenario 1: Developer starts a brand-new project with no existing docs.

    Discriminating state: empty tmp_path — no .git/, no .forge/, no manifests.
    Expected mode: bootstrap.
    """

    def test_detect_mode_bootstrap_in_empty(self, tmp_path):
        """R-SC1-03: empty directory must report mode 'bootstrap'."""
        result = detect_mode(tmp_path)
        assert result == "bootstrap"

    def test_creates_arquitectura_docs(self, tmp_path):
        """R-SC1-04 + R-SC1-06: bootstrap flow creates architecture docs and
        read_overview returns content; vision_skipped is False by default."""
        create_audit_config(tmp_path, [], None, None, "", pending_detection=True)
        result = create_arquitectura_docs(tmp_path, "overview content", "stack content")

        assert (tmp_path / "docs" / "arquitectura" / "overview.md").exists()
        assert (tmp_path / "docs" / "arquitectura" / "stack.md").exists()
        assert "overview" in result["created"]
        assert "stack" in result["created"]

        # R-SC1-06: read_overview returns the content; is_vision_skipped defaults False
        overview_text = read_overview(tmp_path)
        assert overview_text is not None
        assert "overview content" in overview_text
        assert is_vision_skipped(tmp_path) is False

    def test_patches_config_stacks(self, tmp_path):
        """R-SC1-05: patch_config_stacks updates context.stacks in config.yaml."""
        create_audit_config(tmp_path, [], None, None, "", pending_detection=True)
        patched = patch_config_stacks(tmp_path, ["Python"])

        assert patched is True
        config = yaml.safe_load(
            (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        )
        assert config["context"]["stacks"] == ["Python"]

    def test_vision_skipped_path(self, tmp_path):
        """R-SC1-06: mark_vision_skipped toggles is_vision_skipped from False to True."""
        create_audit_config(tmp_path, [], None, None, "", pending_detection=True)

        assert is_vision_skipped(tmp_path) is False
        mark_vision_skipped(tmp_path)
        assert is_vision_skipped(tmp_path) is True


# ---------------------------------------------------------------------------
# Scenario 2: Greenfield — with pre-existing external docs
# ---------------------------------------------------------------------------


class TestScenario2GreenfieldWithDocs:
    """Scenario 2: Developer starts a new project that already has docs (e.g. a PRD).

    Discriminating state: no .git/, but docs/prd.md pre-exists with content.
    Expected mode: bootstrap (greenfield — no .git/ or manifest).
    """

    def _setup_external_doc(self, tmp_path: Path) -> Path:
        """Write an external PRD document at docs/prd.md."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        prd_path = docs_dir / "prd.md"
        prd_path.write_text("# PRD\n\nVision text.", encoding="utf-8")
        return prd_path

    def test_external_doc_preserved(self, tmp_path):
        """R-SC2-03: external doc at docs/prd.md must survive the bootstrap helper chain."""
        prd_path = self._setup_external_doc(tmp_path)
        original_content = prd_path.read_text(encoding="utf-8")

        create_audit_config(tmp_path, [], None, None, "", pending_detection=True)
        mark_vision_skipped(tmp_path)
        create_arquitectura_docs(tmp_path, "overview content", "stack content")

        assert prd_path.exists()
        assert prd_path.read_text(encoding="utf-8") == original_content

    def test_read_overview_after_create(self, tmp_path):
        """R-SC2-04 + R-SC2-05: after creating arch docs, read_overview returns content;
        detect_mode still reports 'bootstrap' (no .git/ present)."""
        self._setup_external_doc(tmp_path)
        create_audit_config(tmp_path, [], None, None, "", pending_detection=True)
        create_arquitectura_docs(tmp_path, "overview content", "stack content")

        overview = read_overview(tmp_path)
        assert overview is not None
        assert "overview content" in overview

        # R-SC2-05: mode is still bootstrap — no .git/ was created
        assert detect_mode(tmp_path) == "bootstrap"


# ---------------------------------------------------------------------------
# Scenario 3: Existing system — adopt mode
# ---------------------------------------------------------------------------


class TestScenario3ExistingSystem:
    """Scenario 3: Developer runs forge on an existing project that has .git/ and manifests.

    Discriminating state: .git/ dir + pyproject.toml (no .forge/).
    Expected mode: adopt.
    """

    def _setup_existing_project(self, tmp_path: Path) -> None:
        """Create the discriminating filesystem state for an existing project."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n", encoding="utf-8")

    def test_detect_mode_adopt_with_git_manifest(self, tmp_path):
        """R-SC3-03: .git/ + pyproject.toml must report mode 'adopt'."""
        self._setup_existing_project(tmp_path)
        result = detect_mode(tmp_path)
        assert result == "adopt"

    def test_is_legacy_returns_false(self, tmp_path):
        """R-SC3-04: existing system with no legacy flags must not be detected as legacy."""
        self._setup_existing_project(tmp_path)
        create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")
        assert is_legacy_project(tmp_path) is False

    def test_vision_not_skipped_by_default(self, tmp_path):
        """R-SC3-05: is_vision_skipped defaults to False when mark_vision_skipped was never called."""
        self._setup_existing_project(tmp_path)
        create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")
        assert is_vision_skipped(tmp_path) is False


# ---------------------------------------------------------------------------
# Scenario 4: Legacy system
# ---------------------------------------------------------------------------


class TestScenario4Legacy:
    """Scenario 4: Developer runs forge on a legacy project.

    Discriminating state: .git/ + pyproject.toml + legacy marker (config or frontmatter).
    Expected mode: adopt (legacy is orthogonal to mode — does not change it).

    Setup is self-contained and independent from TestScenario3 (D-05, NF-03).
    """

    def _setup_legacy_base(self, tmp_path: Path) -> None:
        """Create the base filesystem state for a legacy project (independent of SC3)."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "pyproject.toml").write_text("[project]\nname = \"legacy-app\"\n", encoding="utf-8")

    def test_legacy_via_config(self, tmp_path):
        """R-SC4-04 + R-SC4-03: setting is_legacy: true in config marks project as legacy;
        detect_mode still returns 'adopt' (legacy is orthogonal to mode)."""
        self._setup_legacy_base(tmp_path)
        create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")

        # Write is_legacy: true directly into config.yaml
        config_path = tmp_path / "docs" / "auditoria" / "config.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config.setdefault("context", {})["is_legacy"] = True
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        assert is_legacy_project(tmp_path) is True
        # R-SC4-03: mode stays 'adopt' even with legacy flag on
        assert detect_mode(tmp_path) == "adopt"

    def test_legacy_via_frontmatter(self, tmp_path):
        """R-SC4-05: is_legacy_project detects legacy: true in overview.md YAML frontmatter."""
        self._setup_legacy_base(tmp_path)

        overview_dir = tmp_path / "docs" / "arquitectura"
        overview_dir.mkdir(parents=True, exist_ok=True)
        (overview_dir / "overview.md").write_text(
            "---\nlegacy: true\n---\n# Overview\nLegacy system context.\n",
            encoding="utf-8",
        )

        assert is_legacy_project(tmp_path) is True

    def test_detect_mode_still_adopt(self, tmp_path):
        """R-SC4-03 standalone: detect_mode returns 'adopt' for a legacy project with .git/."""
        self._setup_legacy_base(tmp_path)
        create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")

        # Mark as legacy via config
        config_path = tmp_path / "docs" / "auditoria" / "config.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config.setdefault("context", {})["is_legacy"] = True
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        assert is_legacy_project(tmp_path) is True
        assert detect_mode(tmp_path) == "adopt"
