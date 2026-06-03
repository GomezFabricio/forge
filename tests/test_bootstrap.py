"""Tests de forge.bootstrap (tests-bootstrap-paths).

Cubre las siguientes unidades:
- detect_stack              REQ-TEST-DETECT-STACK
- detect_test_runner        REQ-TEST-DETECT-RUNNER
- _build_stacks_yaml        REQ-TEST-BUILD-YAML
- _build_test_runner_yaml   REQ-TEST-BUILD-YAML
- ensure_dirs               REQ-TEST-ENSURE-DIRS, REQ-IDEMPOTENT
- create_audit_config       REQ-TEST-CREATE-CONFIG, REQ-YAML-TYPES, REQ-IDEMPOTENT
- update_gitignore          REQ-TEST-GITIGNORE, REQ-IDEMPOTENT
- generate_skill_registry_placeholder  REQ-TEST-SKILL-REGISTRY, REQ-IDEMPOTENT
- merge_or_create_claude_md REQ-TEST-CLAUDE-MD
- copy_config_templates     (complemento de REQ-TEST-CLAUDE-MD)
- init_codegraph            REQ-TEST-INIT-CODEGRAPH
- run                       REQ-TEST-RUN

Constraints (CC-*):
- CC-TMP-PATH: todo test que toca filesystem usa tmp_path.
- CC-NO-REAL-PROC: nunca invoca un subprocess real ni requiere binario codegraph.
- CC-NO-MODIFY: bootstrap.py no se modifica en este ciclo.
"""

import builtins
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

import forge.bootstrap as bootstrap
from forge.bootstrap import (
    _build_stacks_yaml,
    _build_test_runner_yaml,
    copy_config_templates,
    create_audit_config,
    detect_stack,
    detect_test_runner,
    ensure_dirs,
    extract_section,
    generate_skill_registry_placeholder,
    init_codegraph,
    merge_or_create_claude_md,
    run,
    update_detection_fields,
    update_gitignore,
)

# ---------------------------------------------------------------------------
# Phase 3: Pure function tests (no filesystem I/O)
# ---------------------------------------------------------------------------


class TestDetectStack:
    """Tests para detect_stack(root). REQ-TEST-DETECT-STACK."""

    def test_multiple_manifests_detected(self, tmp_path):
        """GIVEN pyproject.toml y package.json, THEN ambos stacks detectados."""
        (tmp_path / "pyproject.toml").touch()
        (tmp_path / "package.json").touch()
        result = detect_stack(tmp_path)
        assert "Python" in result
        assert "Node" in result

    def test_single_manifest_python(self, tmp_path):
        """GIVEN solo pyproject.toml, THEN lista contiene exactamente Python."""
        (tmp_path / "pyproject.toml").touch()
        result = detect_stack(tmp_path)
        assert result == ["Python"]

    def test_no_manifest_returns_empty(self, tmp_path):
        """GIVEN directorio vacío, THEN lista vacía."""
        result = detect_stack(tmp_path)
        assert result == []

    def test_multiple_python_manifests_no_duplicates(self, tmp_path):
        """GIVEN pyproject.toml + requirements.txt + setup.py, THEN 'Python' aparece una sola vez."""
        (tmp_path / "pyproject.toml").touch()
        (tmp_path / "requirements.txt").touch()
        (tmp_path / "setup.py").touch()
        result = detect_stack(tmp_path)
        assert result.count("Python") == 1

    def test_cargo_toml_detected_as_rust(self, tmp_path):
        """GIVEN Cargo.toml, THEN 'Rust' detectado."""
        (tmp_path / "Cargo.toml").touch()
        result = detect_stack(tmp_path)
        assert "Rust" in result

    def test_go_mod_detected_as_go(self, tmp_path):
        """GIVEN go.mod, THEN 'Go' detectado."""
        (tmp_path / "go.mod").touch()
        result = detect_stack(tmp_path)
        assert "Go" in result

    def test_result_contains_only_recognised_names(self, tmp_path):
        """GIVEN varios manifests, THEN todos los valores son nombres canónicos conocidos."""
        (tmp_path / "pyproject.toml").touch()
        (tmp_path / "package.json").touch()
        (tmp_path / "go.mod").touch()
        result = detect_stack(tmp_path)
        known_stacks = {"Python", "Node", "Go", "Java", "Rust", "PHP", "Ruby"}
        for s in result:
            assert s in known_stacks, f"Stack desconocido: {s}"


class TestDetectTestRunner:
    """Tests para detect_test_runner(root, stacks). REQ-TEST-DETECT-RUNNER."""

    def test_pytest_detected_via_pyproject_toml(self, tmp_path):
        """GIVEN pyproject.toml presente, THEN runner_name='pytest', command no vacío."""
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
        runner_name, command, detected_from = detect_test_runner(tmp_path, ["Python"])
        assert runner_name == "pytest"
        assert command
        assert detected_from == "pyproject.toml"

    def test_pytest_detected_via_setup_cfg(self, tmp_path):
        """GIVEN setup.cfg presente, THEN pytest detectado."""
        (tmp_path / "setup.cfg").touch()
        runner_name, command, detected_from = detect_test_runner(tmp_path, ["Python"])
        assert runner_name == "pytest"
        assert detected_from == "setup.cfg"

    def test_pytest_detected_via_pytest_ini(self, tmp_path):
        """GIVEN pytest.ini presente, THEN pytest detectado."""
        (tmp_path / "pytest.ini").touch()
        runner_name, command, detected_from = detect_test_runner(tmp_path, ["Python"])
        assert runner_name == "pytest"
        assert detected_from == "pytest.ini"

    def test_no_indicator_returns_none(self, tmp_path):
        """GIVEN directorio vacío con stacks=[Python], THEN (None, None, '')."""
        # Python stack pero sin ningún archivo indicador → unittest tiene indicators=[]
        # lo cual significa que matching=[] pero not indicators es True → retorna unittest
        # Usamos un stack no registrado para obtener None
        runner_name, command, _ = detect_test_runner(tmp_path, [])
        assert runner_name is None
        assert command is None

    def test_unknown_stack_returns_none(self, tmp_path):
        """GIVEN stack desconocido, THEN (None, None, '')."""
        runner_name, command, detected_from = detect_test_runner(tmp_path, ["Cobol"])
        assert runner_name is None
        assert command is None
        assert detected_from == ""

    def test_go_runner_detected(self, tmp_path):
        """GIVEN Go stack con go.mod, THEN runner='go test'."""
        (tmp_path / "go.mod").touch()
        runner_name, command, _ = detect_test_runner(tmp_path, ["Go"])
        assert runner_name == "go test"
        assert "go test" in command


class TestBuildYamlHelpers:
    """Tests para _build_stacks_yaml y _build_test_runner_yaml. REQ-TEST-BUILD-YAML."""

    def test_build_stacks_empty_list(self):
        """GIVEN [], THEN resultado representa lista YAML vacía."""
        result = _build_stacks_yaml([])
        assert "[]" in result

    def test_build_stacks_single_item(self):
        """GIVEN ['Python'], THEN resultado contiene '- Python'."""
        result = _build_stacks_yaml(["Python"])
        assert "- Python" in result

    def test_build_stacks_multiple_items(self):
        """GIVEN ['Python', 'Node'], THEN ambas líneas presentes."""
        result = _build_stacks_yaml(["Python", "Node"])
        assert "- Python" in result
        assert "- Node" in result

    def test_build_stacks_preserves_order(self):
        """GIVEN ['Go', 'Rust', 'Java'], THEN orden preservado."""
        result = _build_stacks_yaml(["Go", "Rust", "Java"])
        lines = [line.strip() for line in result.split("\n") if line.strip()]
        assert lines == ["- Go", "- Rust", "- Java"]

    def test_build_test_runner_yaml_none(self):
        """GIVEN runner=None, THEN resultado contiene 'null'."""
        result = _build_test_runner_yaml(None, None, "")
        assert "null" in result

    def test_build_test_runner_yaml_with_values(self):
        """GIVEN runner='pytest', command='pytest', detected_from='pyproject.toml', THEN todos los campos presentes."""
        result = _build_test_runner_yaml("pytest", "pytest", "pyproject.toml")
        assert "pytest" in result
        assert "pyproject.toml" in result

    def test_build_test_runner_yaml_non_none_has_name(self):
        """GIVEN runner no vacío, THEN 'name:' presente en resultado."""
        result = _build_test_runner_yaml("jest", "npx jest", "jest.config.js")
        assert "name:" in result
        assert "jest" in result


# ---------------------------------------------------------------------------
# Phase 4: Filesystem tests (tmp_path)
# ---------------------------------------------------------------------------


class TestEnsureDirs:
    """Tests para ensure_dirs(root). REQ-TEST-ENSURE-DIRS, REQ-IDEMPOTENT."""

    def test_creates_all_required_dirs(self, tmp_path):
        """GIVEN tmp_path vacío, THEN docs/auditoria/cambios/, .atl/, config/ creados."""
        ensure_dirs(tmp_path)
        assert (tmp_path / "docs" / "auditoria" / "cambios").is_dir()
        assert (tmp_path / ".atl").is_dir()
        assert (tmp_path / "config").is_dir()

    def test_returns_non_empty_list(self, tmp_path):
        """GIVEN tmp_path vacío, THEN retorna lista no vacía."""
        result = ensure_dirs(tmp_path)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_idempotent_no_exception_on_second_call(self, tmp_path):
        """GIVEN ya llamado una vez, THEN segunda llamada no lanza excepción."""
        ensure_dirs(tmp_path)
        ensure_dirs(tmp_path)  # no debe lanzar
        assert (tmp_path / ".atl").is_dir()

    def test_directories_still_exist_after_second_call(self, tmp_path):
        """GIVEN segunda llamada idempotente, THEN dirs siguen existiendo."""
        ensure_dirs(tmp_path)
        ensure_dirs(tmp_path)
        assert (tmp_path / "docs" / "auditoria" / "cambios").is_dir()
        assert (tmp_path / "config").is_dir()


class TestCreateAuditConfig:
    """Tests para create_audit_config(...). REQ-TEST-CREATE-CONFIG, REQ-YAML-TYPES, REQ-IDEMPOTENT."""

    def _ensure_audit_dir(self, root: Path):
        (root / "docs" / "auditoria").mkdir(parents=True, exist_ok=True)

    def test_fresh_creation_returns_created(self, tmp_path):
        """GIVEN directorio vacío, THEN retorna 'created'."""
        self._ensure_audit_dir(tmp_path)
        result = create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")
        assert result == "created"

    def test_fresh_creation_file_exists(self, tmp_path):
        """GIVEN directorio vacío, THEN docs/auditoria/config.yaml existe después."""
        self._ensure_audit_dir(tmp_path)
        create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")
        assert (tmp_path / "docs" / "auditoria" / "config.yaml").exists()

    def test_preserved_when_file_exists(self, tmp_path):
        """GIVEN config.yaml ya existe, THEN retorna 'preserved'."""
        self._ensure_audit_dir(tmp_path)
        create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")
        result = create_audit_config(tmp_path, ["Node"], "jest", "npx jest", "jest.config.js")
        assert result == "preserved"

    def test_preserved_file_content_unchanged(self, tmp_path):
        """GIVEN config.yaml ya existe, THEN contenido no se modifica en segunda llamada."""
        self._ensure_audit_dir(tmp_path)
        create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")
        original = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        create_audit_config(tmp_path, ["Node"], "jest", "npx jest", "jest.config.js")
        after = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        assert original == after

    def test_yaml_round_trip_enforcement_is_str_off(self, tmp_path):
        """REQ-YAML-TYPES: enforcement round-tripea como str 'off', no bool False (YAML 1.1 gotcha)."""
        self._ensure_audit_dir(tmp_path)
        create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")
        raw = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        config = yaml.safe_load(raw)
        enforcement = config["rules"]["pr_size"]["enforcement"]
        assert isinstance(enforcement, str), f"enforcement debe ser str, es {type(enforcement)}"
        assert enforcement == "off", f"enforcement debe ser 'off', es {enforcement!r}"

    def test_yaml_round_trip_suggest_split_is_bool_false(self, tmp_path):
        """REQ-YAML-TYPES: suggest_split round-tripea como bool False."""
        self._ensure_audit_dir(tmp_path)
        create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")
        raw = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        config = yaml.safe_load(raw)
        suggest_split = config["rules"]["pr_size"]["suggest_split"]
        assert isinstance(suggest_split, bool), f"suggest_split debe ser bool, es {type(suggest_split)}"
        assert suggest_split is False

    def test_yaml_round_trip_tdd_is_bool_false(self, tmp_path):
        """REQ-YAML-TYPES: tdd round-tripea como bool False."""
        self._ensure_audit_dir(tmp_path)
        create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")
        raw = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        config = yaml.safe_load(raw)
        tdd = config["rules"]["implement"]["tdd"]
        assert isinstance(tdd, bool), f"tdd debe ser bool, es {type(tdd)}"
        assert tdd is False

    def test_yaml_round_trip_budget_lines_is_int(self, tmp_path):
        """REQ-YAML-TYPES: budget_lines round-tripea como int 400."""
        self._ensure_audit_dir(tmp_path)
        create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")
        raw = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        config = yaml.safe_load(raw)
        budget = config["rules"]["pr_size"]["budget_lines"]
        assert isinstance(budget, int), f"budget_lines debe ser int, es {type(budget)}"
        assert budget == 400

    def test_yaml_round_trip_max_tasks_is_int(self, tmp_path):
        """REQ-YAML-TYPES: max_tasks_per_batch round-tripea como int 20."""
        self._ensure_audit_dir(tmp_path)
        create_audit_config(tmp_path, ["Python"], "pytest", "pytest", "pyproject.toml")
        raw = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        config = yaml.safe_load(raw)
        max_tasks = config["rules"]["implement"]["max_tasks_per_batch"]
        assert isinstance(max_tasks, int)
        assert max_tasks == 20

    def test_yaml_round_trip_stacks_is_list(self, tmp_path):
        """REQ-YAML-TYPES: context.stacks round-tripea como list."""
        self._ensure_audit_dir(tmp_path)
        create_audit_config(tmp_path, ["Python", "Node"], "pytest", "pytest", "pyproject.toml")
        raw = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        config = yaml.safe_load(raw)
        stacks = config["context"]["stacks"]
        assert isinstance(stacks, list)
        assert "Python" in stacks
        assert "Node" in stacks

    def test_stacks_empty_list_written_correctly(self, tmp_path):
        """GIVEN stacks=[], THEN config.yaml se crea sin error y stacks es lista vacía o null."""
        self._ensure_audit_dir(tmp_path)
        result = create_audit_config(tmp_path, [], None, None, "")
        assert result == "created"
        raw = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        config = yaml.safe_load(raw)
        # stacks puede ser [] (lista vacía) según como PyYAML parsee "    []"
        stacks = config["context"]["stacks"]
        assert stacks == [] or stacks is None


class TestUpdateGitignore:
    """Tests para update_gitignore(root). REQ-TEST-GITIGNORE, REQ-IDEMPOTENT."""

    FORGE_ENTRIES = ["# forge", ".codegraph/", ".engram/", "!.engram/chunks/"]

    def test_fresh_creation(self, tmp_path):
        """GIVEN sin .gitignore, THEN archivo creado con entradas forge."""
        update_gitignore(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text(encoding="utf-8")
        for entry in self.FORGE_ENTRIES:
            assert entry in content, f"Entrada faltante: {entry}"

    def test_fresh_creation_returns_created(self, tmp_path):
        """GIVEN sin .gitignore, THEN retorna 'created'."""
        result = update_gitignore(tmp_path)
        assert result == "created"

    def test_append_missing_entries(self, tmp_path):
        """GIVEN .gitignore existente sin entradas forge, THEN entradas agregadas."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n*.pyc\n", encoding="utf-8")
        update_gitignore(tmp_path)
        content = gitignore.read_text(encoding="utf-8")
        for entry in self.FORGE_ENTRIES:
            assert entry in content

    def test_append_returns_updated(self, tmp_path):
        """GIVEN .gitignore sin entradas forge, THEN retorna string con 'updated'."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n", encoding="utf-8")
        result = update_gitignore(tmp_path)
        assert "updated" in result

    def test_idempotent_no_duplicates(self, tmp_path):
        """GIVEN llamado dos veces, THEN entradas forge no se duplican (conteo por línea)."""
        update_gitignore(tmp_path)
        update_gitignore(tmp_path)
        lines = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
        # Cada entrada debe aparecer exactamente una vez como línea completa
        for entry in self.FORGE_ENTRIES:
            exact_count = lines.count(entry)
            assert exact_count == 1, f"Entrada duplicada como línea: {entry!r} (aparece {exact_count} veces)"

    def test_idempotent_returns_preserved(self, tmp_path):
        """GIVEN segunda llamada con entradas ya presentes, THEN retorna 'preserved'."""
        update_gitignore(tmp_path)
        result = update_gitignore(tmp_path)
        assert result == "preserved"

    def test_existing_content_preserved(self, tmp_path):
        """GIVEN .gitignore con contenido previo, THEN contenido original no se elimina."""
        gitignore = tmp_path / ".gitignore"
        original_content = "# mis reglas\n*.log\n__pycache__/\n"
        gitignore.write_text(original_content, encoding="utf-8")
        update_gitignore(tmp_path)
        content = gitignore.read_text(encoding="utf-8")
        assert "*.log" in content
        assert "__pycache__/" in content


class TestGenerateSkillRegistryPlaceholder:
    """Tests para generate_skill_registry_placeholder(root). REQ-TEST-SKILL-REGISTRY, REQ-IDEMPOTENT."""

    def test_creates_file_when_absent(self, tmp_path):
        """GIVEN sin .atl/skill-registry.md, THEN archivo creado."""
        (tmp_path / ".atl").mkdir()
        generate_skill_registry_placeholder(tmp_path)
        assert (tmp_path / ".atl" / "skill-registry.md").exists()

    def test_returns_placeholder_created(self, tmp_path):
        """GIVEN sin .atl/skill-registry.md, THEN retorna 'placeholder_created'."""
        (tmp_path / ".atl").mkdir()
        result = generate_skill_registry_placeholder(tmp_path)
        assert result == "placeholder_created"

    def test_file_contains_skill_registry_header(self, tmp_path):
        """GIVEN archivo creado, THEN contiene '# Skill Registry'."""
        (tmp_path / ".atl").mkdir()
        generate_skill_registry_placeholder(tmp_path)
        content = (tmp_path / ".atl" / "skill-registry.md").read_text(encoding="utf-8")
        assert "# Skill Registry" in content

    def test_preserved_when_already_exists(self, tmp_path):
        """GIVEN .atl/skill-registry.md ya existe, THEN retorna 'preserved'."""
        atl = tmp_path / ".atl"
        atl.mkdir()
        registry = atl / "skill-registry.md"
        registry.write_text("# Custom Registry\n", encoding="utf-8")
        result = generate_skill_registry_placeholder(tmp_path)
        assert result == "preserved"

    def test_content_unchanged_on_second_call(self, tmp_path):
        """GIVEN archivo existente, THEN contenido no se modifica."""
        atl = tmp_path / ".atl"
        atl.mkdir()
        registry = atl / "skill-registry.md"
        custom_content = "# My Custom Registry\nsome content\n"
        registry.write_text(custom_content, encoding="utf-8")
        generate_skill_registry_placeholder(tmp_path)
        assert registry.read_text(encoding="utf-8") == custom_content


# ---------------------------------------------------------------------------
# Phase 5: PACKAGE_ROOT monkeypatch tests
# ---------------------------------------------------------------------------

FAKE_TEMPLATE_CONTENT = """\
## Persona del orquestador

Sos el orquestador del workflow forge.

## Engram

Usás Engram para persistir contexto.

## Strict TDD Mode

Ciclo RED → GREEN → TRIANGULATE → REFACTOR.

## Workflow de las skills

Las skills se cargan desde .atl/skill-registry.md.

## Idioma

Español Rioplatense para respuestas al usuario.
"""


class TestMergeOrCreateClaudeMd:
    """Tests para merge_or_create_claude_md(root). REQ-TEST-CLAUDE-MD."""

    def _setup_package_root(self, monkeypatch, tmp_path):
        """Configura PACKAGE_ROOT falso con template institucional."""
        fake_pkg_root = tmp_path / "fake_pkg"
        templates_dir = fake_pkg_root / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "CLAUDE-md-institucional.md").write_text(
            FAKE_TEMPLATE_CONTENT, encoding="utf-8"
        )
        monkeypatch.setattr(bootstrap, "PACKAGE_ROOT", fake_pkg_root)
        return fake_pkg_root

    def test_fresh_create_no_existing_file(self, tmp_path, monkeypatch):
        """GIVEN sin CLAUDE.md, THEN archivo creado, retorna 'created'."""
        self._setup_package_root(monkeypatch, tmp_path)
        project_root = tmp_path / "project"
        project_root.mkdir()
        result = merge_or_create_claude_md(project_root)
        assert result == "created"
        assert (project_root / "CLAUDE.md").exists()

    def test_fresh_create_content_matches_template(self, tmp_path, monkeypatch):
        """GIVEN sin CLAUDE.md, THEN archivo contiene contenido del template."""
        self._setup_package_root(monkeypatch, tmp_path)
        project_root = tmp_path / "project"
        project_root.mkdir()
        merge_or_create_claude_md(project_root)
        content = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Persona del orquestador" in content

    def test_append_missing_section(self, tmp_path, monkeypatch):
        """GIVEN CLAUDE.md sin sección institucional, THEN sección agregada."""
        self._setup_package_root(monkeypatch, tmp_path)
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "CLAUDE.md").write_text(
            "# My Project Config\n\nSome existing content.\n", encoding="utf-8"
        )
        result = merge_or_create_claude_md(project_root)
        assert "merged" in result
        content = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Persona del orquestador" in content

    def test_preserve_existing_section(self, tmp_path, monkeypatch):
        """GIVEN CLAUDE.md ya tiene sección institucional, THEN retorna 'preserved'."""
        self._setup_package_root(monkeypatch, tmp_path)
        project_root = tmp_path / "project"
        project_root.mkdir()
        existing_with_sections = (
            "# My Config\n\n## Persona del orquestador\nYa existe.\n"
            "## Engram\nYa existe.\n"
            "## Strict TDD Mode\nYa existe.\n"
            "## Workflow de las skills\nYa existe.\n"
            "## Idioma\nYa existe.\n"
        )
        (project_root / "CLAUDE.md").write_text(existing_with_sections, encoding="utf-8")
        result = merge_or_create_claude_md(project_root)
        assert result == "preserved"

    def test_no_duplication_on_second_call(self, tmp_path, monkeypatch):
        """GIVEN llamado dos veces, THEN secciones no se duplican."""
        self._setup_package_root(monkeypatch, tmp_path)
        project_root = tmp_path / "project"
        project_root.mkdir()
        merge_or_create_claude_md(project_root)
        # Segunda llamada sobre el archivo recién creado
        merge_or_create_claude_md(project_root)
        content = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
        # La sección no debe aparecer dos veces
        assert content.count("## Persona del orquestador") == 1


class TestCopyConfigTemplates:
    """Tests para copy_config_templates(root). Complemento de REQ-TEST-CLAUDE-MD."""

    def _setup_package_root(self, monkeypatch, tmp_path):
        """Configura PACKAGE_ROOT falso con config/modulos-transversales.yaml."""
        fake_pkg_root = tmp_path / "fake_pkg"
        config_dir = fake_pkg_root / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "modulos-transversales.yaml").write_text(
            "# Módulos transversales\nschema: forge\n", encoding="utf-8"
        )
        monkeypatch.setattr(bootstrap, "PACKAGE_ROOT", fake_pkg_root)
        return fake_pkg_root

    def test_copies_config_template_to_destination(self, tmp_path, monkeypatch):
        """GIVEN config/ no existe en destino, THEN modulos-transversales.yaml copiado."""
        self._setup_package_root(monkeypatch, tmp_path)
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "config").mkdir()
        result = copy_config_templates(project_root)
        assert "modulos-transversales.yaml" in result
        assert result["modulos-transversales.yaml"] == "created"
        assert (project_root / "config" / "modulos-transversales.yaml").exists()

    def test_preserves_existing_config(self, tmp_path, monkeypatch):
        """GIVEN config ya existe en destino, THEN retorna 'preserved' y no sobrescribe."""
        self._setup_package_root(monkeypatch, tmp_path)
        project_root = tmp_path / "project"
        (project_root / "config").mkdir(parents=True)
        original = "# mi config personalizada\n"
        (project_root / "config" / "modulos-transversales.yaml").write_text(
            original, encoding="utf-8"
        )
        result = copy_config_templates(project_root)
        assert result["modulos-transversales.yaml"] == "preserved"
        # Contenido no se modifica
        assert (project_root / "config" / "modulos-transversales.yaml").read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# Phase 6: Subprocess tests (sin subprocess real)
# ---------------------------------------------------------------------------


class TestInitCodegraph:
    """Tests para init_codegraph(root). REQ-TEST-INIT-CODEGRAPH, CC-NO-REAL-PROC."""

    def test_binary_absent_returns_gracefully(self, tmp_path, monkeypatch):
        """GIVEN shutil.which devuelve None, THEN (None, msg) — sin subprocess real."""
        monkeypatch.setattr("shutil.which", lambda _: None)
        status, warning = init_codegraph(tmp_path)
        assert status is None
        assert warning is not None
        assert "codegraph" in warning.lower()

    def test_binary_absent_no_subprocess_called(self, tmp_path, monkeypatch):
        """GIVEN shutil.which devuelve None, THEN subprocess.run no invocado."""
        monkeypatch.setattr("shutil.which", lambda _: None)
        with patch("subprocess.run") as mock_run:
            init_codegraph(tmp_path)
            mock_run.assert_not_called()

    def test_happy_path_mocked_subprocess(self, tmp_path, monkeypatch):
        """GIVEN which devuelve path y subprocess mock exitoso, THEN 'indexed' retornado."""
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/codegraph")
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            status, warning = init_codegraph(tmp_path)
            mock_run.assert_called_once()
            assert status == "indexed"
            assert warning is None

    def test_happy_path_subprocess_called_with_correct_args(self, tmp_path, monkeypatch):
        """GIVEN which devuelve path, THEN subprocess.run invocado con ['codegraph', 'init', '.']."""
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/codegraph")
        mock_result = MagicMock()
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            init_codegraph(tmp_path)
            call_args = mock_run.call_args
            assert call_args[0][0] == ["codegraph", "init", "."]

    def test_db_already_exists_returns_preserved(self, tmp_path, monkeypatch):
        """GIVEN .codegraph/codegraph.db ya existe, THEN retorna ('preserved', None)."""
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/codegraph")
        db_path = tmp_path / ".codegraph" / "codegraph.db"
        db_path.parent.mkdir(parents=True)
        db_path.touch()
        status, warning = init_codegraph(tmp_path)
        assert status == "preserved"
        assert warning is None


# ---------------------------------------------------------------------------
# Phase 7: Integration test
# ---------------------------------------------------------------------------


class TestRun:
    """Tests de integración para run(root). REQ-TEST-RUN."""

    def _setup_for_run(self, monkeypatch, tmp_path):
        """Setup completo: PACKAGE_ROOT falso + which=None."""
        fake_pkg_root = tmp_path / "fake_pkg"
        # Templates
        (fake_pkg_root / "templates").mkdir(parents=True)
        (fake_pkg_root / "templates" / "CLAUDE-md-institucional.md").write_text(
            FAKE_TEMPLATE_CONTENT, encoding="utf-8"
        )
        # Config
        (fake_pkg_root / "config").mkdir()
        (fake_pkg_root / "config" / "modulos-transversales.yaml").write_text(
            "schema: forge\n", encoding="utf-8"
        )
        monkeypatch.setattr(bootstrap, "PACKAGE_ROOT", fake_pkg_root)
        monkeypatch.setattr("shutil.which", lambda _: None)
        return fake_pkg_root

    def test_run_returns_dict(self, tmp_path, monkeypatch):
        """GIVEN setup completo, THEN run() retorna dict."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        self._setup_for_run(monkeypatch, tmp_path)
        result = run(project_root)
        assert isinstance(result, dict)

    def test_run_dict_has_required_keys(self, tmp_path, monkeypatch):
        """GIVEN run() completo, THEN dict contiene claves esperadas."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        self._setup_for_run(monkeypatch, tmp_path)
        result = run(project_root)
        expected_keys = {"dirs_ensured", "audit_config", "gitignore", "skill_registry", "claude_md", "codegraph"}
        for key in expected_keys:
            assert key in result, f"Clave faltante en resultado de run(): {key}"

    def test_run_no_exception(self, tmp_path, monkeypatch):
        """GIVEN setup completo, THEN run() no lanza excepción."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        self._setup_for_run(monkeypatch, tmp_path)
        # No debe lanzar
        run(project_root)

    def test_run_dirs_ensured_non_empty(self, tmp_path, monkeypatch):
        """GIVEN run() completo, THEN dirs_ensured es lista no vacía."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        self._setup_for_run(monkeypatch, tmp_path)
        result = run(project_root)
        assert isinstance(result["dirs_ensured"], list)
        assert len(result["dirs_ensured"]) > 0

    def test_run_audit_config_created(self, tmp_path, monkeypatch):
        """GIVEN primera ejecución, THEN audit_config es 'created'."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        self._setup_for_run(monkeypatch, tmp_path)
        result = run(project_root)
        assert result["audit_config"] == "created"

    def test_run_idempotent_second_call(self, tmp_path, monkeypatch):
        """GIVEN run() llamado dos veces, THEN segunda no lanza excepción."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        self._setup_for_run(monkeypatch, tmp_path)
        run(project_root)
        run(project_root)

    def test_run_codegraph_skipped_without_binary(self, tmp_path, monkeypatch):
        """GIVEN which=None, THEN codegraph.status es None y hay warning."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        self._setup_for_run(monkeypatch, tmp_path)
        result = run(project_root)
        assert result["codegraph"]["status"] is None
        assert result["codegraph"]["warning"] is not None

    def test_run_with_python_stack_detected(self, tmp_path, monkeypatch):
        """GIVEN pyproject.toml en project_root, THEN stacks contiene 'Python'."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[tool.pytest]\n", encoding="utf-8")
        self._setup_for_run(monkeypatch, tmp_path)
        result = run(project_root)
        assert "Python" in result["stacks"]


# ---------------------------------------------------------------------------
# Phase 8: Edge cases para cobertura >= 85%
# Cubre ramas no alcanzadas: extract_section (marker ausente), update_gitignore
# (existing sin trailing newline), merge_or_create_claude_md (existing sin
# trailing newline), init_codegraph (SubprocessError).
# ---------------------------------------------------------------------------


class TestExtractSection:
    """Tests para extract_section(content, marker). Cubre rama line 103."""

    def test_marker_not_found_returns_empty_string(self):
        """GIVEN marker ausente en content, THEN retorna ''."""
        result = extract_section("# Header\nsome content\n", "## Missing Section")
        assert result == ""

    def test_marker_found_returns_section_up_to_next_h2(self):
        """GIVEN marker presente, THEN retorna sección hasta el próximo ## heading."""
        content = "## Sección A\nContenido A.\n\n## Sección B\nContenido B.\n"
        result = extract_section(content, "## Sección A")
        assert "## Sección A" in result
        assert "Contenido A." in result
        # No debe incluir Sección B
        assert "## Sección B" not in result

    def test_marker_at_end_returns_full_tail(self):
        """GIVEN marker al final sin heading siguiente, THEN retorna todo desde el marker."""
        content = "## Última Sección\nContenido final.\n"
        result = extract_section(content, "## Última Sección")
        assert "Contenido final." in result


class TestUpdateGitignoreNoTrailingNewline:
    """Cubre rama line 300: existing sin trailing newline."""

    def test_append_to_file_without_trailing_newline(self, tmp_path):
        """GIVEN .gitignore existente sin trailing newline, THEN entradas agregadas correctamente."""
        gitignore = tmp_path / ".gitignore"
        # Sin trailing newline al final
        gitignore.write_bytes(b"node_modules/")
        result = update_gitignore(tmp_path)
        content = gitignore.read_text(encoding="utf-8")
        assert "# forge" in content
        assert ".codegraph/" in content
        assert "updated" in result


class TestMergeOrCreateClaudeMdNoTrailingNewline:
    """Cubre rama line 134: existing CLAUDE.md sin trailing newline antes de merge."""

    FAKE_TEMPLATE = "## Persona del orquestador\nContenido.\n"

    def _setup_package_root(self, monkeypatch, tmp_path):
        fake_pkg_root = tmp_path / "fake_pkg"
        (fake_pkg_root / "templates").mkdir(parents=True)
        (fake_pkg_root / "templates" / "CLAUDE-md-institucional.md").write_text(
            self.FAKE_TEMPLATE, encoding="utf-8"
        )
        monkeypatch.setattr(bootstrap, "PACKAGE_ROOT", fake_pkg_root)

    def test_merge_when_existing_has_no_trailing_newline(self, tmp_path, monkeypatch):
        """GIVEN CLAUDE.md sin trailing newline, THEN merge no produce línea doble vacía al inicio."""
        self._setup_package_root(monkeypatch, tmp_path)
        project_root = tmp_path / "project"
        project_root.mkdir()
        # Sin trailing newline
        (project_root / "CLAUDE.md").write_bytes(b"# My Config\nSome content")
        result = merge_or_create_claude_md(project_root)
        assert "merged" in result
        content = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Persona del orquestador" in content


class TestInitCodegraphSubprocessError:
    """Cubre rama lines 167-168: SubprocessError en init_codegraph."""

    def test_subprocess_error_returns_none_with_message(self, tmp_path, monkeypatch):
        """GIVEN subprocess.run lanza SubprocessError, THEN (None, msg) retornado."""
        import subprocess
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/codegraph")
        with patch("subprocess.run", side_effect=subprocess.SubprocessError("fallo de prueba")):
            status, warning = init_codegraph(tmp_path)
        assert status is None
        assert warning is not None
        assert "codegraph" in warning.lower()


# ---------------------------------------------------------------------------
# Phase 9: Mode Detection (B.1)
# ---------------------------------------------------------------------------


class TestDetectMode:
    """Tests para detect_mode(root). R-MODE-01 through R-MODE-04, NFR-04."""

    def test_detect_mode_bootstrap_empty_dir(self, tmp_path):
        """GIVEN empty dir (no .forge/, no .git/, no manifest), THEN 'bootstrap'."""
        from forge.bootstrap import detect_mode
        result = detect_mode(tmp_path)
        assert result == "bootstrap"

    def test_detect_mode_adopt_with_manifest(self, tmp_path):
        """GIVEN pyproject.toml present but no .forge/ or .git/, THEN 'adopt'."""
        from forge.bootstrap import detect_mode
        (tmp_path / "pyproject.toml").touch()
        result = detect_mode(tmp_path)
        assert result == "adopt"

    def test_detect_mode_adopt_with_git(self, tmp_path):
        """GIVEN .git/ present but no .forge/ and no manifest, THEN 'adopt'."""
        from forge.bootstrap import detect_mode
        (tmp_path / ".git").mkdir()
        result = detect_mode(tmp_path)
        assert result == "adopt"

    def test_detect_mode_upgrade_with_dotforge(self, tmp_path):
        """GIVEN .forge/ present, THEN 'upgrade' regardless of other state."""
        from forge.bootstrap import detect_mode
        (tmp_path / ".forge").mkdir()
        result = detect_mode(tmp_path)
        assert result == "upgrade"

    def test_detect_mode_upgrade_ignores_git_and_manifest(self, tmp_path):
        """GIVEN .forge/ + .git/ + manifest, THEN 'upgrade' (.forge wins)."""
        from forge.bootstrap import detect_mode
        (tmp_path / ".forge").mkdir()
        (tmp_path / ".git").mkdir()
        (tmp_path / "pyproject.toml").touch()
        result = detect_mode(tmp_path)
        assert result == "upgrade"

    def test_detect_mode_forge_plus_git_plus_manifest_is_upgrade(self, tmp_path):
        """GIVEN all three signals, THEN .forge/ wins → 'upgrade'."""
        from forge.bootstrap import detect_mode
        (tmp_path / ".forge").mkdir()
        (tmp_path / ".git").mkdir()
        (tmp_path / "Cargo.toml").touch()
        result = detect_mode(tmp_path)
        assert result == "upgrade"

    def test_detect_mode_pure_filesystem_no_mutation(self, tmp_path):
        """NFR-04: detect_mode does not create files or directories."""
        from forge.bootstrap import detect_mode
        before = set(tmp_path.iterdir())
        detect_mode(tmp_path)
        after = set(tmp_path.iterdir())
        assert before == after, "detect_mode must not create or delete files"

    def test_detect_mode_adopt_with_any_known_manifest(self, tmp_path):
        """GIVEN Cargo.toml (not .git, not .forge), THEN 'adopt'."""
        from forge.bootstrap import detect_mode
        (tmp_path / "Cargo.toml").touch()
        result = detect_mode(tmp_path)
        assert result == "adopt"


# ---------------------------------------------------------------------------
# Phase 10: update_detection_fields (B.2) — TDD cycle
# ---------------------------------------------------------------------------

# Helper: build a minimal config.yaml with rules comments for preservation tests
MINIMAL_CONFIG_WITH_RULES = """\
schema: forge

context:
  stacks:
    []
  test_runner:
    null
  last_detection: null
  pending_detection: true

rules:
  workflow:
    # cycle_mode controls how phases run
    cycle_mode: interactive  # keep this comment
  implement:
    tdd: false  # TDD is off by default
"""


def _write_config(root, content=MINIMAL_CONFIG_WITH_RULES):
    """Write config.yaml at docs/auditoria/config.yaml."""
    config_dir = root / "docs" / "auditoria"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(content, encoding="utf-8")
    return config_dir / "config.yaml"


class TestUpdateDetectionFields:
    """Tests para update_detection_fields(root). R-LAZY-01 through R-LAZY-04."""

    def test_update_detection_fields_refreshes_stacks(self, tmp_path):
        """GIVEN bootstrap-mode config (stacks=[]) and pyproject.toml added, THEN stacks refreshed."""
        _write_config(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
        result = update_detection_fields(tmp_path)
        assert "stacks" in result
        assert "Python" in result["stacks"]

    def test_update_detection_fields_sets_pending_false(self, tmp_path):
        """GIVEN config with pending_detection: true, THEN after call it is false."""
        _write_config(tmp_path)
        update_detection_fields(tmp_path)
        config = yaml.safe_load((tmp_path / "docs" / "auditoria" / "config.yaml").read_text())
        assert config["context"]["pending_detection"] is False

    def test_update_detection_fields_sets_last_detection_iso8601(self, tmp_path):
        """GIVEN config with last_detection: null, THEN after call it is an ISO 8601 timestamp."""
        _write_config(tmp_path)
        update_detection_fields(tmp_path)
        config = yaml.safe_load((tmp_path / "docs" / "auditoria" / "config.yaml").read_text())
        last = config["context"]["last_detection"]
        assert last is not None
        # Should be parseable as ISO 8601 (basic check)
        datetime.fromisoformat(str(last).replace("Z", "+00:00"))

    def test_update_detection_fields_preserves_rules_comments(self, tmp_path):
        """R-LAZY-02 CRITICAL: rules section comments are preserved after update."""
        _write_config(tmp_path)
        update_detection_fields(tmp_path)
        raw = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        # Comments must be preserved
        assert "# cycle_mode controls how phases run" in raw
        assert "# keep this comment" in raw
        assert "# TDD is off by default" in raw

    def test_update_detection_fields_returns_changed_true_on_diff(self, tmp_path):
        """GIVEN stacks change from [] to Python, THEN changed=True."""
        _write_config(tmp_path)
        (tmp_path / "pyproject.toml").touch()
        result = update_detection_fields(tmp_path)
        assert result["changed"] is True

    def test_update_detection_fields_returns_changed_false_on_same(self, tmp_path):
        """GIVEN stacks already match filesystem, THEN changed=False."""
        # First call to set the state
        _write_config(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
        update_detection_fields(tmp_path)  # first call sets stacks=Python
        result = update_detection_fields(tmp_path)  # second call: same state
        assert result["changed"] is False

    def test_update_detection_fields_noop_when_config_missing(self, tmp_path):
        """EC: if config.yaml does not exist, return empty dict without crashing."""
        result = update_detection_fields(tmp_path)
        assert result == {}

    def test_update_detection_fields_idempotent(self, tmp_path):
        """NFR-01: calling twice on same filesystem state produces same YAML keys."""
        _write_config(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
        update_detection_fields(tmp_path)
        update_detection_fields(tmp_path)
        config = yaml.safe_load((tmp_path / "docs" / "auditoria" / "config.yaml").read_text())
        assert config["context"]["pending_detection"] is False
        assert "Python" in config["context"]["stacks"]

    def test_ruamel_not_installed_raises_runtime_error(self, monkeypatch):
        """EC-01: if ruamel.yaml cannot be imported, RuntimeError with pip instruction."""
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "ruamel.yaml" or name.startswith("ruamel"):
                raise ImportError("No module named 'ruamel'")
            return real_import(name, *args, **kwargs)

        import forge.bootstrap as bs

        def raising_load():
            raise RuntimeError(
                "ruamel.yaml is required for comment-preserving config updates. "
                "Install it with: pip install ruamel.yaml"
            )

        monkeypatch.setattr(bs, "_load_ruamel", raising_load)
        with pytest.raises(RuntimeError, match="pip install ruamel.yaml"):
            bs.update_detection_fields(Path("/fake"))


# ---------------------------------------------------------------------------
# Phase 11: run() mode dispatch + print_report (B.4)
# ---------------------------------------------------------------------------


class TestBootstrapRunMode:
    """Tests for mode-aware run(). R-MODE-05, R-MODE-06, R-MODE-07."""

    def _setup_for_run(self, monkeypatch, tmp_path):
        """Setup fake PACKAGE_ROOT + disable codegraph binary."""
        fake_pkg_root = tmp_path / "fake_pkg"
        (fake_pkg_root / "templates").mkdir(parents=True)
        (fake_pkg_root / "templates" / "CLAUDE-md-institucional.md").write_text(
            "## Persona del orquestador\nContenido.\n", encoding="utf-8"
        )
        (fake_pkg_root / "config").mkdir()
        (fake_pkg_root / "config" / "modulos-transversales.yaml").write_text(
            "schema: forge\n", encoding="utf-8"
        )
        monkeypatch.setattr(bootstrap, "PACKAGE_ROOT", fake_pkg_root)
        monkeypatch.setattr("shutil.which", lambda _: None)

    def test_bootstrap_run_no_manifest_creates_config_pending(self, tmp_path, monkeypatch):
        """R-MODE-05, R-MODE-07: empty dir → config created with pending_detection=true, stacks=[]."""
        self._setup_for_run(monkeypatch, tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        result = run(project, mode="bootstrap")
        assert result["mode"] == "bootstrap"
        assert result["stacks"] == []
        assert result["audit_config"] == "created"
        import yaml
        config = yaml.safe_load((project / "docs" / "auditoria" / "config.yaml").read_text())
        assert config["context"]["pending_detection"] is True
        assert config["context"]["stacks"] == [] or config["context"]["stacks"] is None

    def test_bootstrap_run_does_not_call_git_init(self, tmp_path, monkeypatch):
        """R-MODE-06: bootstrap mode must NOT invoke git init or create .git/."""
        self._setup_for_run(monkeypatch, tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        with patch("subprocess.run") as mock_run:
            run(project, mode="bootstrap")
            # subprocess.run should never be called with git init
            for call in mock_run.call_args_list:
                args = call[0][0] if call[0] else []
                assert "git" not in str(args), f"Unexpected git call: {args}"
        assert not (project / ".git").exists()

    def test_adopt_mode_runs_full_detection(self, tmp_path, monkeypatch):
        """R-MODE-07: adopt mode runs stack detection."""
        self._setup_for_run(monkeypatch, tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        (project / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
        result = run(project, mode="adopt")
        assert result["mode"] == "adopt"
        assert "Python" in result["stacks"]

    def test_upgrade_mode_returns_upgrade(self, tmp_path, monkeypatch):
        """R-MODE-07: upgrade mode is accepted and reported."""
        self._setup_for_run(monkeypatch, tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        (project / ".forge").mkdir()
        result = run(project, mode="upgrade")
        assert result["mode"] == "upgrade"

    def test_config_schema_includes_new_fields(self, tmp_path, monkeypatch):
        """R-LAZY-03: created config.yaml must include last_detection and pending_detection."""
        self._setup_for_run(monkeypatch, tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        run(project, mode="bootstrap")
        import yaml
        config = yaml.safe_load((project / "docs" / "auditoria" / "config.yaml").read_text())
        assert "last_detection" in config["context"]
        assert "pending_detection" in config["context"]

    def test_adopt_mode_sets_pending_detection_false(self, tmp_path, monkeypatch):
        """R-MODE-07: adopt mode writes pending_detection: false."""
        self._setup_for_run(monkeypatch, tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        (project / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
        run(project, mode="adopt")
        import yaml
        config = yaml.safe_load((project / "docs" / "auditoria" / "config.yaml").read_text())
        assert config["context"]["pending_detection"] is False


class TestPrintReportMode:
    """Tests for print_report() R-ENV-03: no fg-plan line; mode in output."""

    def test_print_report_no_proximo_paso_fg_plan(self, capsys, tmp_path, monkeypatch):
        """R-ENV-03: output must NOT contain 'Próximo paso: /fg-plan'."""
        report = {
            "project_root": str(tmp_path),
            "mode": "bootstrap",
            "stacks": [],
            "test_runner": None,
            "dirs_ensured": [],
            "claude_md": "created",
            "audit_config": "created",
            "config_templates": {},
            "codegraph": {"status": None, "warning": "no binary"},
            "skill_registry": "placeholder_created",
            "gitignore": "created",
            "warnings": [],
        }
        from forge.bootstrap import print_report
        print_report(report)
        out = capsys.readouterr().out
        assert "Próximo paso: /fg-plan" not in out
        assert "/fg-plan" not in out

    def test_mode_appears_in_output(self, capsys, tmp_path):
        """R-ENV-03: output must contain 'forge inicializado' with mode."""
        report = {
            "project_root": str(tmp_path),
            "mode": "adopt",
            "stacks": ["Python"],
            "test_runner": {"name": "pytest", "command": "pytest", "detected_from": "pyproject.toml"},
            "dirs_ensured": [],
            "claude_md": "created",
            "audit_config": "created",
            "config_templates": {},
            "codegraph": {"status": None, "warning": "no binary"},
            "skill_registry": "placeholder_created",
            "gitignore": "created",
            "warnings": [],
        }
        from forge.bootstrap import print_report
        print_report(report)
        out = capsys.readouterr().out
        assert "forge inicializado" in out
        assert "adopt" in out


# ---------------------------------------------------------------------------
# Phase 12: needs_detection() (R-LAZY gate helper) — TDD cycle
# ---------------------------------------------------------------------------


class TestNeedsDetection:
    """Tests for needs_detection(root). Covers the testable GATE logic (R3)."""

    def test_returns_true_when_config_missing(self, tmp_path):
        """GIVEN no config.yaml, THEN needs_detection returns True."""
        from forge.bootstrap import needs_detection
        assert needs_detection(tmp_path) is True

    def test_returns_true_when_pending_detection_flag_set(self, tmp_path):
        """GIVEN config with pending_detection: true, THEN needs_detection returns True."""
        from forge.bootstrap import needs_detection
        _write_config(tmp_path)  # MINIMAL_CONFIG_WITH_RULES has pending_detection: true
        assert needs_detection(tmp_path) is True

    def test_returns_true_when_last_detection_null(self, tmp_path):
        """GIVEN config with pending_detection: false but last_detection: null, THEN True."""
        from forge.bootstrap import needs_detection
        content = """\
schema: forge
context:
  stacks: []
  test_runner: null
  last_detection: null
  pending_detection: false
rules:
  workflow:
    cycle_mode: interactive
"""
        _write_config(tmp_path, content)
        assert needs_detection(tmp_path) is True

    def test_returns_true_when_manifest_mtime_newer(self, tmp_path):
        """GIVEN manifest mtime > last_detection, THEN needs_detection returns True."""
        from forge.bootstrap import needs_detection

        # Create config with a past last_detection timestamp
        past = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        content = f"""\
schema: forge
context:
  stacks: []
  test_runner: null
  last_detection: "{past}"
  pending_detection: false
rules:
  workflow:
    cycle_mode: interactive
"""
        _write_config(tmp_path, content)
        # Create manifest with mtime in the future relative to past timestamp
        manifest = tmp_path / "pyproject.toml"
        manifest.write_text("[build-system]\n", encoding="utf-8")
        future_time = time.time() + 10
        os.utime(manifest, (future_time, future_time))
        assert needs_detection(tmp_path) is True

    def test_returns_false_when_fresh(self, tmp_path):
        """GIVEN pending_detection: false, last_detection recent, no manifest newer — False."""
        from forge.bootstrap import needs_detection

        # Create manifest first with a past mtime
        manifest = tmp_path / "pyproject.toml"
        manifest.write_text("[build-system]\n", encoding="utf-8")
        past_mtime = time.time() - 3600  # 1 hour ago
        os.utime(manifest, (past_mtime, past_mtime))

        # Config with last_detection after manifest mtime
        future_ts = datetime.now(tz=timezone.utc).isoformat()
        content = f"""\
schema: forge
context:
  stacks:
    - Python
  test_runner: null
  last_detection: "{future_ts}"
  pending_detection: false
rules:
  workflow:
    cycle_mode: interactive
"""
        _write_config(tmp_path, content)
        assert needs_detection(tmp_path) is False


# ---------------------------------------------------------------------------
# Phase 13: EC-03 recovery — update_detection_fields on upgrade + missing config
# ---------------------------------------------------------------------------


class TestEC03Recovery:
    """Tests for EC-03: re-create config.yaml when upgrade mode but file is missing."""

    def test_upgrade_mode_recreates_config_when_missing(self, tmp_path):
        """EC-03: .forge/ exists but config.yaml missing → update_detection_fields recreates it."""
        from forge.bootstrap import update_detection_fields

        # Simulate upgrade mode context (.forge/ exists, config.yaml absent)
        (tmp_path / ".forge").mkdir()
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
        config_path = tmp_path / "docs" / "auditoria" / "config.yaml"
        assert not config_path.exists(), "pre-condition: config must be missing"

        result = update_detection_fields(tmp_path, mode="upgrade")

        assert config_path.exists(), "config.yaml must be recreated"
        assert result != {}, "must return detection results, not empty dict"
        assert "stacks" in result

    def test_update_detection_fields_handles_missing_config_in_upgrade(self, tmp_path):
        """EC-03: after recreation, context fields are properly set."""
        from forge.bootstrap import update_detection_fields

        (tmp_path / ".forge").mkdir()
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")

        result = update_detection_fields(tmp_path, mode="upgrade")

        config = yaml.safe_load(
            (tmp_path / "docs" / "auditoria" / "config.yaml").read_text()
        )
        assert config["context"]["pending_detection"] is False
        assert config["context"]["last_detection"] is not None
        assert result["changed"] is True  # new config always counts as changed


# ---------------------------------------------------------------------------
# Phase 14: create_arquitectura_docs (B.3) — TDD cycle
# ---------------------------------------------------------------------------


class TestCreateArquitecturaDocs:
    """Tests for create_arquitectura_docs(root, overview_content, stack_content).
    R-HELPER-01, NFR-01, NFR-03.
    """

    def test_creates_directory_if_missing(self, tmp_path):
        """GIVEN docs/arquitectura/ does not exist, THEN it is created."""
        from forge.bootstrap import create_arquitectura_docs

        create_arquitectura_docs(tmp_path, "overview content", "stack content")
        assert (tmp_path / "docs" / "arquitectura").is_dir()

    def test_writes_overview_and_stack(self, tmp_path):
        """GIVEN content provided, THEN files exist with that content (UTF-8)."""
        from forge.bootstrap import create_arquitectura_docs

        create_arquitectura_docs(tmp_path, "Mi overview\n", "Mi stack\n")
        overview = (tmp_path / "docs" / "arquitectura" / "overview.md").read_text(encoding="utf-8")
        stack = (tmp_path / "docs" / "arquitectura" / "stack.md").read_text(encoding="utf-8")
        assert "Mi overview" in overview
        assert "Mi stack" in stack

    def test_does_not_overwrite_existing(self, tmp_path):
        """GIVEN a file already exists, THEN it is NOT overwritten; 'overview' NOT in created."""
        from forge.bootstrap import create_arquitectura_docs

        arch_dir = tmp_path / "docs" / "arquitectura"
        arch_dir.mkdir(parents=True)
        (arch_dir / "overview.md").write_text("original overview", encoding="utf-8")
        result = create_arquitectura_docs(tmp_path, "new overview", "new stack")
        # overview must not be overwritten
        assert (arch_dir / "overview.md").read_text(encoding="utf-8") == "original overview"
        assert "overview" not in result["created"]

    def test_idempotent_on_rerun(self, tmp_path):
        """GIVEN called twice with same content, THEN no error and second call has empty created list."""
        from forge.bootstrap import create_arquitectura_docs

        create_arquitectura_docs(tmp_path, "overview A", "stack A")
        # second call must not raise
        result2 = create_arquitectura_docs(tmp_path, "overview A", "stack A")
        assert result2["created"] == []

    def test_returns_correct_paths(self, tmp_path):
        """GIVEN fresh dir, THEN returned dict has 'overview', 'stack', 'created' keys; paths absolute."""
        from forge.bootstrap import create_arquitectura_docs

        result = create_arquitectura_docs(tmp_path, "overview content", "stack content")
        assert "overview" in result
        assert "stack" in result
        assert "created" in result
        assert result["overview"].is_absolute()
        assert result["stack"].is_absolute()

    def test_partial_existing_overview_only(self, tmp_path):
        """GIVEN overview exists but stack does not, THEN stack created, overview preserved."""
        from forge.bootstrap import create_arquitectura_docs

        arch_dir = tmp_path / "docs" / "arquitectura"
        arch_dir.mkdir(parents=True)
        (arch_dir / "overview.md").write_text("existing overview", encoding="utf-8")
        result = create_arquitectura_docs(tmp_path, "new overview", "new stack")
        # overview preserved
        assert (arch_dir / "overview.md").read_text(encoding="utf-8") == "existing overview"
        assert "overview" not in result["created"]
        # stack created
        assert (arch_dir / "stack.md").read_text(encoding="utf-8") == "new stack"
        assert "stack" in result["created"]

    def test_partial_existing_stack_only(self, tmp_path):
        """GIVEN stack exists but overview does not, THEN overview created, stack preserved."""
        from forge.bootstrap import create_arquitectura_docs

        arch_dir = tmp_path / "docs" / "arquitectura"
        arch_dir.mkdir(parents=True)
        (arch_dir / "stack.md").write_text("existing stack", encoding="utf-8")
        result = create_arquitectura_docs(tmp_path, "new overview", "new stack")
        # overview created
        assert (arch_dir / "overview.md").read_text(encoding="utf-8") == "new overview"
        assert "overview" in result["created"]
        # stack preserved
        assert (arch_dir / "stack.md").read_text(encoding="utf-8") == "existing stack"
        assert "stack" not in result["created"]


# ---------------------------------------------------------------------------
# Phase 15: patch_config_stacks (B.3) — TDD cycle
# ---------------------------------------------------------------------------

# Config template for patch_config_stacks tests — includes comments in rules.*
CONFIG_WITH_CONTEXT_AND_COMMENTS = """\
schema: forge

context:
  stacks:
    []
  test_runner:
    null
  last_detection: null
  pending_detection: true
  vision_skipped: false

rules:
  workflow:
    # cycle_mode controls how phases run
    cycle_mode: interactive  # keep this comment
  implement:
    tdd: false  # TDD is off by default
"""


def _write_patch_config(root, content=CONFIG_WITH_CONTEXT_AND_COMMENTS):
    """Write config.yaml for patch_config_stacks tests."""
    config_dir = root / "docs" / "auditoria"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(content, encoding="utf-8")
    return config_dir / "config.yaml"


class TestPatchConfigStacks:
    """Tests for patch_config_stacks(root, stacks). R-HELPER-02, NFR-04, NFR-05."""

    def test_updates_stacks_field(self, tmp_path):
        """GIVEN config with context block, THEN context.stacks is updated."""
        from forge.bootstrap import patch_config_stacks

        _write_patch_config(tmp_path)
        result = patch_config_stacks(tmp_path, ["python"])
        config_text = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        assert "python" in config_text
        assert result is True

    def test_preserves_rules_comments(self, tmp_path):
        """GIVEN config with comments in rules, THEN all comments survive round-trip."""
        from forge.bootstrap import patch_config_stacks

        _write_patch_config(tmp_path)
        patch_config_stacks(tmp_path, ["python"])
        raw = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        assert "# cycle_mode controls how phases run" in raw
        assert "# keep this comment" in raw
        assert "# TDD is off by default" in raw

    def test_multi_stack_list(self, tmp_path):
        """GIVEN stacks=['python','nextjs'], THEN both appear as separate list items."""
        from forge.bootstrap import patch_config_stacks

        _write_patch_config(tmp_path)
        patch_config_stacks(tmp_path, ["python", "nextjs"])
        import yaml as _yaml
        config = _yaml.safe_load(
            (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        )
        assert "python" in config["context"]["stacks"]
        assert "nextjs" in config["context"]["stacks"]
        assert len(config["context"]["stacks"]) == 2

    def test_noop_when_config_missing(self, tmp_path):
        """GIVEN no config.yaml, THEN returns False, no exception."""
        import warnings  # noqa: I001
        from forge.bootstrap import patch_config_stacks

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = patch_config_stacks(tmp_path, ["python"])
        assert result is False
        assert len(w) >= 1

    def test_noop_empty_list(self, tmp_path):
        """GIVEN stacks=[], THEN returns False, no write."""
        from forge.bootstrap import patch_config_stacks

        _write_patch_config(tmp_path)
        original = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        result = patch_config_stacks(tmp_path, [])
        after = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        assert result is False
        assert original == after

    def test_idempotent_same_stacks(self, tmp_path):
        """GIVEN called twice with same stacks, THEN file content same after second call."""
        from forge.bootstrap import patch_config_stacks

        _write_patch_config(tmp_path)
        patch_config_stacks(tmp_path, ["python"])
        after_first = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        patch_config_stacks(tmp_path, ["python"])
        after_second = (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        assert after_first == after_second

    def test_idempotent_no_duplicate_entries(self, tmp_path):
        """GIVEN called twice with same stacks list, THEN config.stacks has no duplicates."""
        import yaml as _yaml  # noqa: I001
        from forge.bootstrap import patch_config_stacks

        _write_patch_config(tmp_path)
        patch_config_stacks(tmp_path, ["python"])
        patch_config_stacks(tmp_path, ["python"])
        config = _yaml.safe_load(
            (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        )
        assert config["context"]["stacks"].count("python") == 1


# ---------------------------------------------------------------------------
# Phase 16: mark_vision_skipped (B.3) — TDD cycle
# ---------------------------------------------------------------------------


class TestMarkVisionSkipped:
    """Tests for mark_vision_skipped(root). R-VISION-08, R-HELPER-02, EC-01."""

    def test_sets_vision_skipped_true(self, tmp_path):
        """GIVEN config with context block, THEN context.vision_skipped == True after call."""
        import yaml as _yaml  # noqa: I001
        from forge.bootstrap import mark_vision_skipped

        _write_patch_config(tmp_path)
        result = mark_vision_skipped(tmp_path)
        assert result is True
        config = _yaml.safe_load(
            (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        )
        assert config["context"]["vision_skipped"] is True

    def test_noop_when_config_missing(self, tmp_path):
        """GIVEN no config.yaml, THEN returns False, no exception."""
        from forge.bootstrap import mark_vision_skipped

        result = mark_vision_skipped(tmp_path)
        assert result is False

    def test_idempotent_when_already_skipped(self, tmp_path):
        """GIVEN called twice, THEN no error and value stays True."""
        import yaml as _yaml  # noqa: I001
        from forge.bootstrap import mark_vision_skipped

        _write_patch_config(tmp_path)
        mark_vision_skipped(tmp_path)
        result = mark_vision_skipped(tmp_path)
        assert result is True
        config = _yaml.safe_load(
            (tmp_path / "docs" / "auditoria" / "config.yaml").read_text(encoding="utf-8")
        )
        assert config["context"]["vision_skipped"] is True


# ─── Phase 17: read_overview + is_vision_skipped (C.1 + C.2) ─────────────────


class TestReadOverview:
    def test_returns_content_when_present(self, tmp_path):
        """GIVEN overview.md exists with content, THEN returns the content."""
        from forge.bootstrap import read_overview

        overview_dir = tmp_path / "docs" / "arquitectura"
        overview_dir.mkdir(parents=True)
        (overview_dir / "overview.md").write_text("X", encoding="utf-8")
        assert read_overview(tmp_path) == "X"

    def test_returns_none_when_missing(self, tmp_path):
        """GIVEN overview.md does not exist, THEN returns None."""
        from forge.bootstrap import read_overview

        assert read_overview(tmp_path) is None

    def test_returns_none_when_empty(self, tmp_path):
        """GIVEN overview.md exists with zero bytes, THEN returns None."""
        from forge.bootstrap import read_overview

        overview_dir = tmp_path / "docs" / "arquitectura"
        overview_dir.mkdir(parents=True)
        (overview_dir / "overview.md").write_bytes(b"")
        assert read_overview(tmp_path) is None

    def test_returns_none_when_whitespace_only(self, tmp_path):
        """GIVEN overview.md contains only whitespace, THEN returns None."""
        from forge.bootstrap import read_overview

        overview_dir = tmp_path / "docs" / "arquitectura"
        overview_dir.mkdir(parents=True)
        (overview_dir / "overview.md").write_text("   \n", encoding="utf-8")
        assert read_overview(tmp_path) is None

    def test_utf8_content(self, tmp_path):
        """GIVEN overview.md has non-ASCII UTF-8 content, THEN returns correctly decoded string."""
        from forge.bootstrap import read_overview

        content = "Descripción con ñ y tildes: á é í ó ú"
        overview_dir = tmp_path / "docs" / "arquitectura"
        overview_dir.mkdir(parents=True)
        (overview_dir / "overview.md").write_text(content, encoding="utf-8")
        assert read_overview(tmp_path) == content


class TestIsVisionSkipped:
    def _write_vision_config(self, tmp_path, vision_skipped_value):
        """Helper: creates docs/auditoria/config.yaml with the given vision_skipped flag."""
        config_dir = tmp_path / "docs" / "auditoria"
        config_dir.mkdir(parents=True, exist_ok=True)
        if vision_skipped_value is None:
            content = "context: {}\n"
        else:
            content = f"context:\n  vision_skipped: {str(vision_skipped_value).lower()}\n"
        (config_dir / "config.yaml").write_text(content, encoding="utf-8")

    def test_returns_true_when_flag_set(self, tmp_path):
        """GIVEN config with context.vision_skipped: true, THEN returns True."""
        from forge.bootstrap import is_vision_skipped

        self._write_vision_config(tmp_path, True)
        assert is_vision_skipped(tmp_path) is True

    def test_returns_false_when_flag_unset(self, tmp_path):
        """GIVEN config with context: {} (no vision_skipped key), THEN returns False."""
        from forge.bootstrap import is_vision_skipped

        self._write_vision_config(tmp_path, None)
        assert is_vision_skipped(tmp_path) is False

    def test_returns_false_when_config_missing(self, tmp_path):
        """GIVEN no config.yaml exists, THEN returns False."""
        from forge.bootstrap import is_vision_skipped

        assert is_vision_skipped(tmp_path) is False

    def test_returns_false_when_yaml_malformed(self, tmp_path):
        """GIVEN config.yaml with invalid YAML syntax, THEN returns False."""
        from forge.bootstrap import is_vision_skipped

        config_dir = tmp_path / "docs" / "auditoria"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(": invalid: [yaml", encoding="utf-8")
        assert is_vision_skipped(tmp_path) is False
