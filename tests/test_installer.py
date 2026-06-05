"""Tests de forge.installer.

Cubre:
- TestInstallerConstants     — exit codes, paths, prompt text (T01)
- TestDetectEngram           — 3 indicadores, short-circuit, excepciones (T03)
- TestInjectFrontmatter      — función pura, sin mocks (T04)
- TestInstallAssets          — layout fg-*, co-located, forge-shared, agents, idempotencia (T05-T07)
- TestInstallEngram          — platform detection, download, PATH, xattr, MCP, orquestador (T08-T11)
- TestRegisterMcp            — schema FLAT, directorio creado, overwrite (T10)
- TestRun                    — flujos del runner (T12)
- TestDetectCodegraph        — detección vía shutil.which (PR-A T-01/T-02)
- TestCodegraphAssetName     — mapa de assets por plataforma/arch (PR-A T-03/T-04)
- TestVerifySha256           — verificación de integridad SHA256 (PR-A T-05/T-06)

Constraints (CC-*):
- CC-TMP-PATH: filesystem solo en tmp_path.
- CC-NO-REAL-PROC: subprocess siempre mockeado.
- CC-NO-REAL-HOME: monkeypatch Path.home() → tmp_path.
- CC-NO-REAL-HTTP: urllib.request.urlretrieve siempre mockeado.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# T01: TestInstallerConstants
# ---------------------------------------------------------------------------


class TestInstallerConstants:
    """Verifica existencia y valores de constantes de forge.installer. T01."""

    def test_exit_codes_values(self):
        """GIVEN el módulo installer importado WHEN se leen las constantes de exit code
        THEN EXIT_OK=0, EXIT_ABORTED=10, EXIT_ENGRAM_INSTALL_FAILED=20,
             EXIT_DEPOSIT_FAILED=30, EXIT_PLATFORM_UNSUPPORTED=40."""
        from forge import installer
        assert installer.EXIT_OK == 0
        assert installer.EXIT_ABORTED == 10
        assert installer.EXIT_ENGRAM_INSTALL_FAILED == 20
        assert installer.EXIT_DEPOSIT_FAILED == 30
        assert installer.EXIT_PLATFORM_UNSUPPORTED == 40

    def test_path_constants_defined(self):
        """GIVEN el módulo installer WHEN se leen CLAUDE_HOME, MCP_JSON_PATH,
        ENGRAM_BIN_DIR_UNIX, ENGRAM_BIN_DIR_WIN THEN son instancias de Path no vacías."""
        from forge import installer
        assert isinstance(installer.CLAUDE_HOME, Path)
        assert isinstance(installer.MCP_JSON_PATH, Path)
        assert isinstance(installer.ENGRAM_BIN_DIR_UNIX, Path)
        assert isinstance(installer.ENGRAM_BIN_DIR_WIN, Path)

    def test_github_releases_api_defined(self):
        """GIVEN el módulo installer WHEN se lee GITHUB_RELEASES_API
        THEN es una string no vacía que apunta al repo correcto."""
        from forge import installer
        assert isinstance(installer.GITHUB_RELEASES_API, str)
        assert "Gentleman-Programming/engram" in installer.GITHUB_RELEASES_API

    def test_prompt_text_non_empty(self):
        """GIVEN el módulo installer WHEN se lee PROMPT_TEXT
        THEN es una string no vacía."""
        from forge import installer
        assert isinstance(installer.PROMPT_TEXT, str)
        assert len(installer.PROMPT_TEXT.strip()) > 0

    def test_prompt_text_contains_four_numbered_steps(self):
        """GIVEN PROMPT_TEXT WHEN se evalúa su contenido
        THEN contiene los 4 pasos numerados del diseño — REQ-PROMPT-01."""
        from forge import installer
        text = installer.PROMPT_TEXT
        assert "1." in text, "Falta el paso 1 (Descargar binario)"
        assert "2." in text, "Falta el paso 2 (Instalar en path)"
        assert "3." in text, "Falta el paso 3 (Agregar al PATH)"
        assert "4." in text, "Falta el paso 4 (Registrar MCP)"

    def test_prompt_text_contains_manual_install_paragraph(self):
        """GIVEN PROMPT_TEXT WHEN se evalúa su contenido
        THEN contiene el párrafo de alternativa manual — REQ-PROMPT-01."""
        from forge import installer
        text = installer.PROMPT_TEXT
        assert "preferís instalarlo por tu cuenta" in text

    def test_prompt_text_ends_with_yn_prompt(self):
        """GIVEN PROMPT_TEXT WHEN se evalúa su final
        THEN termina con la pregunta [y/N]: — REQ-PROMPT-01."""
        from forge import installer
        text = installer.PROMPT_TEXT
        assert text.rstrip().endswith("[y/N]:") or text.endswith("[y/N]: ")

    def test_prompt_text_contains_engram_bin_path(self):
        """GIVEN PROMPT_TEXT WHEN se evalúa su contenido
        THEN menciona ~/.engram/bin/engram (Unix) y %USERPROFILE% (Windows) — REQ-PROMPT-01."""
        from forge import installer
        text = installer.PROMPT_TEXT
        assert "~/.engram/bin/engram" in text, "Falta la ruta ~/.engram/bin/engram en el prompt Unix"
        assert "%USERPROFILE%" in text, "Falta la ruta %USERPROFILE% en el prompt Windows"

    def test_exit_aborted_no_collision(self):
        """GIVEN EXIT_ABORTED=10 WHEN se compara con exit codes estándar
        THEN no colisiona con pytest (0-5) ni pip (0-3)."""
        from forge import installer
        standard_codes = {0, 1, 2, 3, 4, 5}
        assert installer.EXIT_ABORTED not in standard_codes

    def test_engram_bin_dir_unix_uses_engram_namespace(self):
        """GIVEN el módulo installer WHEN se lee ENGRAM_BIN_DIR_UNIX
        THEN apunta a ~/.engram/bin (no ~/.local/bin) — REQ-INSTALL-ENGRAM-03."""
        from forge import installer
        parts = installer.ENGRAM_BIN_DIR_UNIX.parts
        assert ".engram" in parts, f"Expected .engram in path parts, got: {parts}"
        assert parts[-1] == "bin"
        assert parts[-2] == ".engram"

    def test_engram_bin_path_unix_resolves_correctly(self):
        """GIVEN ENGRAM_BIN_DIR_UNIX WHEN se construye el path al binario
        THEN resulta en ~/.engram/bin/engram — REQ-INSTALL-ENGRAM-03."""
        from forge import installer
        bin_path = installer.ENGRAM_BIN_DIR_UNIX / "engram"
        assert str(bin_path).endswith(".engram/bin/engram") or str(bin_path).endswith(".engram\\bin\\engram")

    def test_engram_bin_dir_unix_and_win_share_namespace(self):
        """GIVEN ENGRAM_BIN_DIR_UNIX y ENGRAM_BIN_DIR_WIN WHEN se comparan sus partes
        THEN ambos usan .engram/bin (consistente entre plataformas) — REQ-INSTALL-ENGRAM-03."""
        from forge import installer
        unix_parts = installer.ENGRAM_BIN_DIR_UNIX.parts
        win_parts = installer.ENGRAM_BIN_DIR_WIN.parts
        assert ".engram" in unix_parts
        assert ".engram" in win_parts
        assert unix_parts[-2:] == (".engram", "bin")
        assert win_parts[-2:] == (".engram", "bin")


# ---------------------------------------------------------------------------
# T03: TestDetectEngram
# ---------------------------------------------------------------------------


class TestDetectEngram:
    """Verifica detect_engram() — 3 indicadores en orden. T03."""

    def test_indicator1_mcp_json_valid_returns_true(self, tmp_path, monkeypatch):
        """GIVEN ~/.claude/mcp/engram.json existe con 'command' apuntando a un ejecutable
        WHEN detect_engram() se llama THEN retorna (True, info) con info['mcp_json'] no nulo."""
        from forge import installer

        mcp_dir = tmp_path / ".claude" / "mcp"
        mcp_dir.mkdir(parents=True)
        binary = tmp_path / "engram_bin"
        binary.write_text("fake binary")
        mcp_file = mcp_dir / "engram.json"
        mcp_file.write_text(json.dumps({"command": str(binary), "args": []}))

        monkeypatch.setattr(installer, "MCP_JSON_PATH", mcp_file)

        found, info = installer.detect_engram()
        assert found is True
        assert info["mcp_json"] == str(binary)

    def test_indicator1_missing_falls_to_indicator2(self, tmp_path, monkeypatch):
        """GIVEN ~/.claude/mcp/engram.json no existe AND shutil.which('engram') retorna un path
        WHEN detect_engram() THEN retorna (True, info) con info['which'] no nulo."""
        from forge import installer

        nonexistent = tmp_path / "no_such.json"
        monkeypatch.setattr(installer, "MCP_JSON_PATH", nonexistent)
        monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/engram")

        found, info = installer.detect_engram()
        assert found is True
        assert info["which"] == "/usr/local/bin/engram"

    def test_indicator1_corrupt_json_falls_to_indicator2(self, tmp_path, monkeypatch):
        """GIVEN engram.json existe pero está corrupto AND which retorna path
        WHEN detect_engram() THEN ignora el JSON corrupto y usa indicador 2."""
        from forge import installer

        mcp_dir = tmp_path / ".claude" / "mcp"
        mcp_dir.mkdir(parents=True)
        mcp_file = mcp_dir / "engram.json"
        mcp_file.write_text("{ invalid json }")
        monkeypatch.setattr(installer, "MCP_JSON_PATH", mcp_file)
        monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/engram")

        found, info = installer.detect_engram()
        assert found is True
        assert info["which"] is not None

    def test_indicator2_missing_falls_to_indicator3(self, tmp_path, monkeypatch):
        """GIVEN indicador 1 y 2 negativos AND engram --version retorna 0
        WHEN detect_engram() THEN retorna (True, info) con info['version_check'] no nulo."""
        from forge import installer

        nonexistent = tmp_path / "no_such.json"
        monkeypatch.setattr(installer, "MCP_JSON_PATH", nonexistent)
        monkeypatch.setattr("shutil.which", lambda _: None)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "engram 1.15.3"

        with patch("subprocess.run", return_value=mock_result):
            found, info = installer.detect_engram()

        assert found is True
        assert info["version_check"] is not None

    def test_all_indicators_negative_returns_false(self, tmp_path, monkeypatch):
        """GIVEN los 3 indicadores negativos WHEN detect_engram() THEN retorna (False, info)."""
        from forge import installer

        nonexistent = tmp_path / "no_such.json"
        monkeypatch.setattr(installer, "MCP_JSON_PATH", nonexistent)
        monkeypatch.setattr("shutil.which", lambda _: None)

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            found, info = installer.detect_engram()

        assert found is False

    def test_timeout_expired_handled_gracefully(self, tmp_path, monkeypatch):
        """GIVEN subprocess.run lanza TimeoutExpired WHEN detect_engram()
        THEN captura la excepción y retorna (False, info)."""
        import subprocess

        from forge import installer

        nonexistent = tmp_path / "no_such.json"
        monkeypatch.setattr(installer, "MCP_JSON_PATH", nonexistent)
        monkeypatch.setattr("shutil.which", lambda _: None)

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["engram"], 5)):
            found, info = installer.detect_engram()

        assert found is False

    def test_file_not_found_handled_gracefully(self, tmp_path, monkeypatch):
        """GIVEN subprocess.run lanza FileNotFoundError WHEN detect_engram()
        THEN captura la excepción y retorna (False, info)."""
        from forge import installer

        nonexistent = tmp_path / "no_such.json"
        monkeypatch.setattr(installer, "MCP_JSON_PATH", nonexistent)
        monkeypatch.setattr("shutil.which", lambda _: None)

        with patch("subprocess.run", side_effect=FileNotFoundError):
            found, info = installer.detect_engram()

        assert found is False

    def test_short_circuit_indicator1_does_not_run_subprocess(self, tmp_path, monkeypatch):
        """GIVEN indicador 1 positivo WHEN detect_engram() THEN subprocess.run NO es llamado."""
        from forge import installer

        mcp_dir = tmp_path / ".claude" / "mcp"
        mcp_dir.mkdir(parents=True)
        binary = tmp_path / "engram_bin"
        binary.write_text("fake")
        mcp_file = mcp_dir / "engram.json"
        mcp_file.write_text(json.dumps({"command": str(binary)}))
        monkeypatch.setattr(installer, "MCP_JSON_PATH", mcp_file)

        with patch("subprocess.run") as mock_run:
            found, _ = installer.detect_engram()
            assert found is True
            mock_run.assert_not_called()

    def test_does_not_modify_filesystem(self, tmp_path, monkeypatch):
        """GIVEN detect_engram() se llama WHEN todos los indicadores son negativos
        THEN el directorio tmp_path no contiene archivos nuevos."""
        from forge import installer

        nonexistent = tmp_path / "no_such.json"
        monkeypatch.setattr(installer, "MCP_JSON_PATH", nonexistent)
        monkeypatch.setattr("shutil.which", lambda _: None)

        files_before = set(tmp_path.rglob("*"))
        with patch("subprocess.run", side_effect=FileNotFoundError):
            installer.detect_engram()
        files_after = set(tmp_path.rglob("*"))
        assert files_before == files_after


# ---------------------------------------------------------------------------
# T04: TestInjectFrontmatter
# ---------------------------------------------------------------------------


class TestInjectFrontmatter:
    """Verifica inject_no_invoke_frontmatter() — función pura. T04."""

    def test_no_frontmatter_prepends_new(self):
        """GIVEN contenido sin frontmatter WHEN inject_no_invoke_frontmatter()
        THEN el resultado empieza con --- y tiene las 2 claves requeridas."""
        from forge.installer import inject_no_invoke_frontmatter
        content = "# My Skill\n\nSome content here.\n"
        result = inject_no_invoke_frontmatter(content)
        assert result.startswith("---\n")
        fm_data = yaml.safe_load(result.split("---\n")[1].split("\n---\n")[0])
        assert fm_data["disable-model-invocation"] is True
        assert fm_data["user-invocable"] is False

    def test_partial_frontmatter_preserves_existing_keys(self):
        """GIVEN frontmatter con 'name' existente WHEN inject THEN preserva 'name'
        y agrega las 2 claves requeridas."""
        from forge.installer import inject_no_invoke_frontmatter
        content = "---\nname: my-skill\ndescription: Does something\n---\n\n# Body\n"
        result = inject_no_invoke_frontmatter(content)
        fm_raw = result.split("---\n")[1].split("\n---\n")[0]
        fm_data = yaml.safe_load(fm_raw)
        assert fm_data["name"] == "my-skill"
        assert fm_data["description"] == "Does something"
        assert fm_data["disable-model-invocation"] is True
        assert fm_data["user-invocable"] is False

    def test_idempotent_when_keys_already_present(self):
        """GIVEN frontmatter con ambas claves ya presentes WHEN inject aplicado 2 veces
        THEN el resultado es el mismo (idempotente)."""
        from forge.installer import inject_no_invoke_frontmatter
        content = "---\ndisable-model-invocation: true\nuser-invocable: false\n---\n\n# Body\n"
        result1 = inject_no_invoke_frontmatter(content)
        result2 = inject_no_invoke_frontmatter(result1)
        assert result1 == result2

    def test_malformed_frontmatter_prepends_new(self):
        """GIVEN frontmatter malformado (sin cierre ---) WHEN inject
        THEN prepende un frontmatter nuevo al inicio."""
        from forge.installer import inject_no_invoke_frontmatter
        content = "---\nname: broken\n# Body sin cierre\n"
        result = inject_no_invoke_frontmatter(content)
        assert result.startswith("---\n")
        # El resultado debe ser parseable
        parts = result.split("---\n")
        assert len(parts) >= 3  # '' + frontmatter + body

    def test_output_parseable_as_yaml(self):
        """GIVEN cualquier input WHEN inject THEN el frontmatter del resultado es
        parseable por yaml.safe_load sin errores."""
        from forge.installer import inject_no_invoke_frontmatter
        contents = [
            "# Sin frontmatter\n",
            "---\nname: test\n---\n\n# Con frontmatter parcial\n",
            "---\ndisable-model-invocation: true\nuser-invocable: false\n---\n# Ya completo\n",
        ]
        for c in contents:
            result = inject_no_invoke_frontmatter(c)
            assert result.startswith("---\n"), f"No empieza con ---\\n: {result[:50]!r}"
            end_idx = result.index("\n---\n", 4)
            fm_raw = result[4:end_idx]
            parsed = yaml.safe_load(fm_raw)
            assert isinstance(parsed, dict)
            assert parsed.get("disable-model-invocation") is True
            assert parsed.get("user-invocable") is False


# ---------------------------------------------------------------------------
# T05-T07: TestInstallAssets
# ---------------------------------------------------------------------------


class TestInstallAssets:
    """Verifica install_assets() — layout, idempotencia, manifest. T05-T07."""

    def _make_share_root(self, tmp_path: Path) -> Path:
        """Crea un share/forge/ de prueba con skills y agents."""
        share = tmp_path / "share" / "forge"
        skills_dir = share / "skills"
        shared_dir = skills_dir / "_shared"
        agents_dir = share / "agents"
        skills_dir.mkdir(parents=True)
        shared_dir.mkdir(parents=True)
        agents_dir.mkdir(parents=True)

        # fg-*.md skills individuales
        for name in ["fg-implement", "fg-review", "fg-plan", "fg-design", "fg-tasks", "fg-setup"]:
            (skills_dir / f"{name}.md").write_text(f"# {name}\n\nContent for {name}.\n")

        # _shared co-located
        (shared_dir / "strict-tdd.md").write_text("# Strict TDD\n\nContent.\n")
        (shared_dir / "strict-tdd-verify.md").write_text("# Strict TDD Verify\n\nContent.\n")

        # _shared cross-cutting
        (shared_dir / "skill-resolver.md").write_text("# Skill Resolver\n\nContent.\n")
        (shared_dir / "engram-protocol.md").write_text("# Engram Protocol\n\nContent.\n")
        (shared_dir / "fg-phase-common.md").write_text("# Phase Common\n\nContent.\n")

        # agents
        for name in ["forge-plan", "forge-design", "forge-implement",
                     "forge-review", "forge-tasks", "forge-setup"]:
            (agents_dir / f"{name}.md").write_text(f"# {name}\n\nAgent content.\n")

        return share

    def test_fg_skills_deposited_as_stem_skill_md(self, tmp_path, monkeypatch):
        """GIVEN fg-implement.md en share/skills/ WHEN install_assets()
        THEN ~/.claude/skills/fg-implement/SKILL.md existe con el contenido correcto."""
        from forge import installer

        share = self._make_share_root(tmp_path)
        claude_home = tmp_path / ".claude"

        monkeypatch.setattr(installer, "get_share_root", lambda: share)
        monkeypatch.setattr(installer, "CLAUDE_HOME", claude_home)

        installer.install_assets()

        skill_file = claude_home / "skills" / "fg-implement" / "SKILL.md"
        assert skill_file.exists()
        assert "fg-implement" in skill_file.read_text()

    def test_all_six_fg_skills_deposited(self, tmp_path, monkeypatch):
        """GIVEN 6 fg-*.md en share/skills/ WHEN install_assets()
        THEN manifest['skills_deposited'] == 6."""
        from forge import installer

        share = self._make_share_root(tmp_path)
        claude_home = tmp_path / ".claude"
        monkeypatch.setattr(installer, "get_share_root", lambda: share)
        monkeypatch.setattr(installer, "CLAUDE_HOME", claude_home)

        manifest = installer.install_assets()
        assert manifest["skills_deposited"] == 6

    def test_agents_deposited_flat(self, tmp_path, monkeypatch):
        """GIVEN agents/*.md en share/agents/ WHEN install_assets()
        THEN ~/.claude/agents/<name>.md existe para cada agent."""
        from forge import installer

        share = self._make_share_root(tmp_path)
        claude_home = tmp_path / ".claude"
        monkeypatch.setattr(installer, "get_share_root", lambda: share)
        monkeypatch.setattr(installer, "CLAUDE_HOME", claude_home)

        manifest = installer.install_assets()

        agents_dir = claude_home / "agents"
        assert (agents_dir / "forge-plan.md").exists()
        assert (agents_dir / "forge-implement.md").exists()
        assert manifest["agents_deposited"] == 6

    def test_idempotent_second_run_no_error(self, tmp_path, monkeypatch):
        """GIVEN install_assets() ya corrió WHEN corre por segunda vez
        THEN no lanza excepción y el resultado es idéntico."""
        from forge import installer

        share = self._make_share_root(tmp_path)
        claude_home = tmp_path / ".claude"
        monkeypatch.setattr(installer, "get_share_root", lambda: share)
        monkeypatch.setattr(installer, "CLAUDE_HOME", claude_home)

        manifest1 = installer.install_assets()
        manifest2 = installer.install_assets()

        assert manifest1["skills_deposited"] == manifest2["skills_deposited"]
        assert manifest1["agents_deposited"] == manifest2["agents_deposited"]

    def test_strict_tdd_md_is_colocated_in_fg_implement(self, tmp_path, monkeypatch):
        """GIVEN _shared/strict-tdd.md WHEN install_assets()
        THEN ~/.claude/skills/fg-implement/strict-tdd.md existe (co-located)."""
        from forge import installer

        share = self._make_share_root(tmp_path)
        claude_home = tmp_path / ".claude"
        monkeypatch.setattr(installer, "get_share_root", lambda: share)
        monkeypatch.setattr(installer, "CLAUDE_HOME", claude_home)

        installer.install_assets()

        colocated = claude_home / "skills" / "fg-implement" / "strict-tdd.md"
        assert colocated.exists()

    def test_strict_tdd_verify_md_is_colocated_in_fg_review(self, tmp_path, monkeypatch):
        """GIVEN _shared/strict-tdd-verify.md WHEN install_assets()
        THEN ~/.claude/skills/fg-review/strict-tdd-verify.md existe."""
        from forge import installer

        share = self._make_share_root(tmp_path)
        claude_home = tmp_path / ".claude"
        monkeypatch.setattr(installer, "get_share_root", lambda: share)
        monkeypatch.setattr(installer, "CLAUDE_HOME", claude_home)

        installer.install_assets()

        colocated = claude_home / "skills" / "fg-review" / "strict-tdd-verify.md"
        assert colocated.exists()

    def test_cross_cutting_deposited_in_forge_shared_with_frontmatter(self, tmp_path, monkeypatch):
        """GIVEN skill-resolver.md en _shared/ WHEN install_assets()
        THEN ~/.claude/skills/forge-shared/skill-resolver/SKILL.md existe con frontmatter inyectado."""
        from forge import installer

        share = self._make_share_root(tmp_path)
        claude_home = tmp_path / ".claude"
        monkeypatch.setattr(installer, "get_share_root", lambda: share)
        monkeypatch.setattr(installer, "CLAUDE_HOME", claude_home)

        installer.install_assets()

        skill_file = claude_home / "skills" / "forge-shared" / "skill-resolver" / "SKILL.md"
        assert skill_file.exists()
        content = skill_file.read_text()
        assert "disable-model-invocation" in content
        assert "user-invocable" in content

    def test_fg_skills_do_not_receive_frontmatter(self, tmp_path, monkeypatch):
        """GIVEN fg-implement.md WHEN install_assets()
        THEN ~/.claude/skills/fg-implement/SKILL.md NO tiene frontmatter inyectado."""
        from forge import installer

        share = self._make_share_root(tmp_path)
        claude_home = tmp_path / ".claude"
        monkeypatch.setattr(installer, "get_share_root", lambda: share)
        monkeypatch.setattr(installer, "CLAUDE_HOME", claude_home)

        installer.install_assets()

        skill_file = claude_home / "skills" / "fg-implement" / "SKILL.md"
        content = skill_file.read_text()
        # No debe tener el frontmatter inyectado — debe ser copia limpia
        assert "disable-model-invocation" not in content

    def test_manifest_has_all_required_keys(self, tmp_path, monkeypatch):
        """GIVEN install_assets() completa WHEN se inspecciona el manifest
        THEN tiene keys: skills_deposited, shared_deposited, agents_deposited, warnings."""
        from forge import installer

        share = self._make_share_root(tmp_path)
        claude_home = tmp_path / ".claude"
        monkeypatch.setattr(installer, "get_share_root", lambda: share)
        monkeypatch.setattr(installer, "CLAUDE_HOME", claude_home)

        manifest = installer.install_assets()

        assert "skills_deposited" in manifest
        assert "shared_deposited" in manifest
        assert "agents_deposited" in manifest
        assert "warnings" in manifest
        assert isinstance(manifest["warnings"], list)

    def test_manifest_shared_count_is_three(self, tmp_path, monkeypatch):
        """GIVEN 3 archivos cross-cutting en _shared/ WHEN install_assets()
        THEN manifest['shared_deposited'] == 3."""
        from forge import installer

        share = self._make_share_root(tmp_path)
        claude_home = tmp_path / ".claude"
        monkeypatch.setattr(installer, "get_share_root", lambda: share)
        monkeypatch.setattr(installer, "CLAUDE_HOME", claude_home)

        manifest = installer.install_assets()
        assert manifest["shared_deposited"] == 3


# ---------------------------------------------------------------------------
# T08: TestDetectPlatform
# ---------------------------------------------------------------------------


class TestDetectPlatform:
    """Verifica _detect_platform() — mapeo OS+arch. T08."""

    def test_linux_x86_64_maps_to_linux_amd64(self, monkeypatch):
        """GIVEN sys.platform='linux' y machine='x86_64'
        WHEN _detect_platform() THEN retorna ('linux', 'amd64')."""
        from forge import installer
        monkeypatch.setattr("sys.platform", "linux")
        with patch("platform.machine", return_value="x86_64"):
            os_tok, arch_tok = installer._detect_platform()
        assert os_tok == "linux"
        assert arch_tok == "amd64"

    def test_darwin_arm64_maps_correctly(self, monkeypatch):
        """GIVEN sys.platform='darwin' y machine='arm64'
        WHEN _detect_platform() THEN retorna ('darwin', 'arm64')."""
        from forge import installer
        monkeypatch.setattr("sys.platform", "darwin")
        with patch("platform.machine", return_value="arm64"):
            os_tok, arch_tok = installer._detect_platform()
        assert os_tok == "darwin"
        assert arch_tok == "arm64"

    def test_win32_maps_to_windows_amd64(self, monkeypatch):
        """GIVEN sys.platform='win32' WHEN _detect_platform()
        THEN retorna ('windows', 'amd64')."""
        from forge import installer
        monkeypatch.setattr("sys.platform", "win32")
        with patch("platform.machine", return_value="AMD64"):
            os_tok, arch_tok = installer._detect_platform()
        assert os_tok == "windows"
        assert arch_tok == "amd64"

    def test_unknown_platform_raises_system_exit(self, monkeypatch):
        """GIVEN plataforma desconocida WHEN _detect_platform()
        THEN lanza SystemExit con EXIT_PLATFORM_UNSUPPORTED."""
        from forge import installer
        monkeypatch.setattr("sys.platform", "freebsd")
        with patch("platform.machine", return_value="x86_64"), \
             pytest.raises(SystemExit) as exc:
            installer._detect_platform()
        assert exc.value.code == installer.EXIT_PLATFORM_UNSUPPORTED


# ---------------------------------------------------------------------------
# T08: TestDownloadBinary (parte de TestInstallEngram)
# ---------------------------------------------------------------------------


class TestDownloadBinary:
    """Verifica _download_binary() — retry, success, fallo. T08."""

    def test_successful_download(self, tmp_path):
        """GIVEN urlretrieve no lanza excepciones WHEN _download_binary()
        THEN el directorio destino se crea y no lanza excepción."""
        from forge import installer
        dest = tmp_path / "bin" / "engram"

        with patch("urllib.request.urlretrieve") as mock_dl:
            installer._download_binary("https://example.com/engram", dest)
            mock_dl.assert_called_once_with("https://example.com/engram", str(dest))

        assert dest.parent.exists()

    def test_retry_on_first_failure(self, tmp_path):
        """GIVEN urlretrieve falla en intento 1 y OK en intento 2
        WHEN _download_binary() THEN retorna sin excepción."""
        import urllib.error

        from forge import installer
        dest = tmp_path / "bin" / "engram"

        call_count = [0]
        def side_effect(url, path):
            call_count[0] += 1
            if call_count[0] == 1:
                raise urllib.error.URLError("network error")

        with patch("urllib.request.urlretrieve", side_effect=side_effect):
            installer._download_binary("https://example.com/engram", dest)

        assert call_count[0] == 2

    def test_raises_after_two_failures(self, tmp_path):
        """GIVEN urlretrieve falla 2 veces WHEN _download_binary()
        THEN lanza la excepción original."""
        import urllib.error

        from forge import installer
        dest = tmp_path / "bin" / "engram"

        with patch("urllib.request.urlretrieve", side_effect=urllib.error.URLError("fail")), \
             pytest.raises(urllib.error.URLError):
            installer._download_binary("https://example.com/engram", dest)


# ---------------------------------------------------------------------------
# T09: TestEditPathUnix
# ---------------------------------------------------------------------------


class TestEditPathUnix:
    """Verifica _edit_path_unix() — append, idempotente, crea. T09."""

    def test_appends_to_existing_profile(self, tmp_path):
        """GIVEN ~/.profile existe sin la entrada de PATH WHEN _edit_path_unix()
        THEN retorna dict con status 'appended' para .profile y la entry está en el archivo."""
        from forge import installer
        profile = tmp_path / ".profile"
        profile.write_text("# existing content\n")
        bin_dir = tmp_path / ".local" / "bin"

        with patch.object(Path, "home", return_value=tmp_path):
            result = installer._edit_path_unix(bin_dir)

        assert result[".profile"] == "appended"
        content = profile.read_text()
        assert str(bin_dir) in content

    def test_idempotent_if_already_present(self, tmp_path):
        """GIVEN ~/.profile ya tiene la entrada de PATH WHEN _edit_path_unix()
        THEN retorna dict con 'present' para .profile y NO agrega duplicado."""
        from forge import installer
        bin_dir = tmp_path / ".local" / "bin"
        profile = tmp_path / ".profile"
        profile.write_text(f'export PATH="{bin_dir}:$PATH"\n')

        with patch.object(Path, "home", return_value=tmp_path):
            result = installer._edit_path_unix(bin_dir)

        assert result[".profile"] == "present"
        content = profile.read_text()
        assert content.count(str(bin_dir)) == 1

    def test_creates_profile_if_missing(self, tmp_path):
        """GIVEN ~/.profile no existe WHEN _edit_path_unix() THEN crea el archivo
        con la entrada y retorna dict con status 'created' para .profile."""
        from forge import installer
        bin_dir = tmp_path / ".local" / "bin"

        with patch.object(Path, "home", return_value=tmp_path):
            result = installer._edit_path_unix(bin_dir)

        assert result[".profile"] == "created"
        profile = tmp_path / ".profile"
        assert profile.exists()
        assert str(bin_dir) in profile.read_text()

    # REQ-PLATFORM-03: los 3 rc files -------------------------------------------

    def test_edits_all_three_rc_files_when_they_exist(self, tmp_path):
        """GIVEN ~/.bashrc, ~/.zshrc y ~/.profile existen sin la entry de PATH
        WHEN _edit_path_unix() THEN edita los 3 archivos — REQ-PLATFORM-03."""
        from forge import installer
        bin_dir = tmp_path / ".engram" / "bin"
        (tmp_path / ".bashrc").write_text("# bashrc\n")
        (tmp_path / ".zshrc").write_text("# zshrc\n")
        (tmp_path / ".profile").write_text("# profile\n")

        with patch.object(Path, "home", return_value=tmp_path):
            result = installer._edit_path_unix(bin_dir)

        assert result[".bashrc"] == "appended"
        assert result[".zshrc"] == "appended"
        assert result[".profile"] == "appended"
        for rc in (".bashrc", ".zshrc", ".profile"):
            assert str(bin_dir) in (tmp_path / rc).read_text()

    def test_idempotent_across_all_rc_files(self, tmp_path):
        """GIVEN los 3 rc files ya tienen la entry de PATH
        WHEN _edit_path_unix() se llama 2 veces THEN no duplica la entry en ninguno."""
        from forge import installer
        bin_dir = tmp_path / ".engram" / "bin"
        export_line = f'export PATH="{bin_dir}:$PATH"\n'
        for rc in (".bashrc", ".zshrc", ".profile"):
            (tmp_path / rc).write_text(export_line)

        with patch.object(Path, "home", return_value=tmp_path):
            result1 = installer._edit_path_unix(bin_dir)
            result2 = installer._edit_path_unix(bin_dir)

        assert all(s == "present" for s in result1.values())
        assert all(s == "present" for s in result2.values())
        for rc in (".bashrc", ".zshrc", ".profile"):
            content = (tmp_path / rc).read_text()
            assert content.count(str(bin_dir)) == 1

    def test_skips_nonexistent_rc_files(self, tmp_path):
        """GIVEN solo ~/.profile existe WHEN _edit_path_unix()
        THEN solo edita .profile — no crea .bashrc ni .zshrc — REQ-PLATFORM-03."""
        from forge import installer
        bin_dir = tmp_path / ".engram" / "bin"
        (tmp_path / ".profile").write_text("# profile\n")

        with patch.object(Path, "home", return_value=tmp_path):
            result = installer._edit_path_unix(bin_dir)

        # .profile editado, .bashrc/.zshrc no creados (no existían)
        assert result[".profile"] == "appended"
        assert ".bashrc" not in result or result[".bashrc"] == "skipped"
        assert not (tmp_path / ".bashrc").exists()
        assert not (tmp_path / ".zshrc").exists()

    def test_export_line_points_to_engram_bin(self, tmp_path):
        """GIVEN _edit_path_unix() WHEN agrega entry en rc files
        THEN la línea export apunta a .engram/bin — REQ-INSTALL-ENGRAM-03."""
        from forge import installer
        bin_dir = tmp_path / ".engram" / "bin"
        (tmp_path / ".bashrc").write_text("# bashrc\n")

        with patch.object(Path, "home", return_value=tmp_path):
            installer._edit_path_unix(bin_dir)

        content = (tmp_path / ".bashrc").read_text()
        assert ".engram" in content
        assert "bin" in content


# ---------------------------------------------------------------------------
# T09: TestXattrCleanup
# ---------------------------------------------------------------------------


class TestXattrCleanup:
    """Verifica _xattr_cleanup_darwin() — best-effort. T09."""

    def test_runs_xattr_on_darwin(self, tmp_path, monkeypatch):
        """GIVEN sys.platform='darwin' WHEN _xattr_cleanup_darwin()
        THEN subprocess.run es invocado con xattr -d."""
        from forge import installer
        monkeypatch.setattr("sys.platform", "darwin")
        binary_path = tmp_path / "engram"

        with patch("subprocess.run") as mock_run:
            installer._xattr_cleanup_darwin(binary_path)
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "xattr" in args
            assert "com.apple.quarantine" in args

    def test_noop_on_non_darwin(self, tmp_path, monkeypatch):
        """GIVEN sys.platform='linux' WHEN _xattr_cleanup_darwin()
        THEN subprocess.run NO es invocado."""
        from forge import installer
        monkeypatch.setattr("sys.platform", "linux")
        binary_path = tmp_path / "engram"

        with patch("subprocess.run") as mock_run:
            installer._xattr_cleanup_darwin(binary_path)
            mock_run.assert_not_called()

    def test_xattr_failure_does_not_raise(self, tmp_path, monkeypatch):
        """GIVEN subprocess.run lanza FileNotFoundError WHEN _xattr_cleanup_darwin()
        THEN no propaga la excepción (best-effort)."""
        from forge import installer
        monkeypatch.setattr("sys.platform", "darwin")
        binary_path = tmp_path / "engram"

        with patch("subprocess.run", side_effect=FileNotFoundError):
            installer._xattr_cleanup_darwin(binary_path)  # no debe lanzar


# ---------------------------------------------------------------------------
# T10: TestRegisterMcp
# ---------------------------------------------------------------------------


class TestRegisterMcp:
    """Verifica register_mcp() — schema FLAT, directorio, overwrite. T10."""

    def test_creates_mcp_json_with_flat_schema(self, tmp_path, monkeypatch):
        """GIVEN directorio mcp no existe WHEN register_mcp()
        THEN crea el JSON con schema flat (command + args top-level)."""
        from forge import installer
        mcp_file = tmp_path / ".claude" / "mcp" / "engram.json"
        monkeypatch.setattr(installer, "MCP_JSON_PATH", mcp_file)

        binary_path = tmp_path / ".local" / "bin" / "engram"
        installer.register_mcp(binary_path)

        assert mcp_file.exists()
        data = json.loads(mcp_file.read_text())
        assert "command" in data
        assert "args" in data
        assert "mcpServers" not in data
        assert data["command"] == str(binary_path)

    def test_creates_parent_directory_if_missing(self, tmp_path, monkeypatch):
        """GIVEN directorio padre no existe WHEN register_mcp()
        THEN crea el directorio y el archivo."""
        from forge import installer
        mcp_file = tmp_path / "deep" / "nested" / "engram.json"
        monkeypatch.setattr(installer, "MCP_JSON_PATH", mcp_file)

        binary_path = tmp_path / "engram"
        installer.register_mcp(binary_path)

        assert mcp_file.exists()

    def test_overwrites_existing_file(self, tmp_path, monkeypatch):
        """GIVEN engram.json ya existe con contenido diferente WHEN register_mcp()
        THEN sobreescribe con el nuevo comando y retorna 'overwritten'."""
        from forge import installer
        mcp_file = tmp_path / "engram.json"
        mcp_file.write_text(json.dumps({"command": "/old/path/engram", "args": []}))
        monkeypatch.setattr(installer, "MCP_JSON_PATH", mcp_file)

        new_binary = tmp_path / "new" / "engram"
        status = installer.register_mcp(new_binary)

        assert status == "overwritten"
        data = json.loads(mcp_file.read_text())
        assert data["command"] == str(new_binary)

    def test_returns_created_for_new_file(self, tmp_path, monkeypatch):
        """GIVEN el archivo no existía WHEN register_mcp() THEN retorna 'created'."""
        from forge import installer
        mcp_file = tmp_path / "engram.json"
        monkeypatch.setattr(installer, "MCP_JSON_PATH", mcp_file)

        binary_path = tmp_path / "engram"
        status = installer.register_mcp(binary_path)
        assert status == "created"

    def test_output_is_valid_json(self, tmp_path, monkeypatch):
        """GIVEN register_mcp() exitoso WHEN se lee el archivo
        THEN es JSON válido con 'args' como lista."""
        from forge import installer
        mcp_file = tmp_path / "engram.json"
        monkeypatch.setattr(installer, "MCP_JSON_PATH", mcp_file)

        binary_path = tmp_path / "engram"
        installer.register_mcp(binary_path)

        data = json.loads(mcp_file.read_text())
        assert isinstance(data["args"], list)
        assert "mcp" in data["args"]


# ---------------------------------------------------------------------------
# T11: TestInstallEngram (orquestador)
# ---------------------------------------------------------------------------


class TestInstallEngram:
    """Verifica install_engram() — happy path y failure. T11."""

    def test_happy_path_calls_all_subfunctions(self, tmp_path, monkeypatch):
        """GIVEN todas las sub-funciones OK WHEN install_engram()
        THEN llama _detect_platform, _download_binary, register_mcp, retorna (True, msg)."""
        from forge import installer

        monkeypatch.setattr(installer, "ENGRAM_BIN_DIR_UNIX", tmp_path / "bin")
        monkeypatch.setattr(installer, "ENGRAM_BIN_DIR_WIN", tmp_path / "bin")

        api_response = MagicMock()
        api_response.read.return_value = json.dumps({
            "assets": [
                {"name": "engram_1.16.1_linux_amd64.tar.gz",
                 "browser_download_url": "https://example.com/engram_1.16.1_linux_amd64.tar.gz"}
            ]
        }).encode()
        api_response.__enter__ = lambda s: s
        api_response.__exit__ = MagicMock(return_value=False)

        # Mock tarfile member extraction
        mock_member = MagicMock()
        mock_member.name = "engram"
        mock_tf = MagicMock()
        mock_tf.__enter__ = lambda s: s
        mock_tf.__exit__ = MagicMock(return_value=False)
        mock_tf.getmembers.return_value = [mock_member]
        mock_tf.extract = MagicMock()

        with patch.object(installer, "_detect_platform", return_value=("linux", "amd64")), \
             patch("urllib.request.urlopen", return_value=api_response), \
             patch.object(installer, "_download_binary"), \
             patch("os.chmod"), \
             patch.object(installer, "_xattr_cleanup_darwin"), \
             patch.object(installer, "_edit_path_unix", return_value="appended"), \
             patch.object(installer, "register_mcp", return_value="created") as m_reg, \
             patch("tarfile.open", return_value=mock_tf), \
             patch("os.unlink"):
            ok, msg = installer.install_engram()

        assert ok is True
        m_reg.assert_called_once()

    def test_download_failure_returns_false(self, tmp_path, monkeypatch):
        """GIVEN _download_binary lanza excepción WHEN install_engram()
        THEN retorna (False, mensaje de error)."""
        import urllib.error

        from forge import installer

        monkeypatch.setattr(installer, "ENGRAM_BIN_DIR_UNIX", tmp_path / "bin")

        api_response = MagicMock()
        api_response.read.return_value = json.dumps({
            "assets": [
                {"name": "engram_1.16.1_linux_amd64.tar.gz",
                 "browser_download_url": "https://example.com/engram_1.16.1_linux_amd64.tar.gz"}
            ]
        }).encode()
        api_response.__enter__ = lambda s: s
        api_response.__exit__ = MagicMock(return_value=False)

        with patch.object(installer, "_detect_platform", return_value=("linux", "amd64")), \
             patch("urllib.request.urlopen", return_value=api_response), \
             patch.object(installer, "_download_binary",
                          side_effect=urllib.error.URLError("no network")):
            ok, msg = installer.install_engram()

        assert ok is False
        assert isinstance(msg, str)
        assert len(msg) > 0


# ---------------------------------------------------------------------------
# T12: TestRun
# ---------------------------------------------------------------------------


class TestRun:
    """Verifica run(args) — todos los branches del flujo. T12."""

    def _make_args(self, install_engram=False, skip_engram_check=False):
        """Helper para crear argparse.Namespace."""
        import argparse
        return argparse.Namespace(
            install_engram=install_engram,
            skip_engram_check=skip_engram_check,
        )

    def test_detect_true_skips_prompt_and_deposits(self, monkeypatch):
        """GIVEN detect_engram retorna True WHEN run() THEN no hay prompt,
        install_assets se llama, retorna EXIT_OK."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(True, {"mcp_json": "/p"})), \
             patch.object(installer, "install_assets", return_value={"skills_deposited": 6,
                                                                      "shared_deposited": 3,
                                                                      "agents_deposited": 6,
                                                                      "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args())

        assert result == installer.EXIT_OK

    def test_detect_false_skip_check_deposits_without_install(self, monkeypatch):
        """GIVEN detect_engram=False y --skip-engram-check WHEN run()
        THEN install_engram NO es llamado, deposit sí, retorna EXIT_OK."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(False, {})), \
             patch.object(installer, "install_engram") as mock_install, \
             patch.object(installer, "install_assets", return_value={"skills_deposited": 6,
                                                                      "shared_deposited": 3,
                                                                      "agents_deposited": 6,
                                                                      "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args(skip_engram_check=True))

        assert result == installer.EXIT_OK
        mock_install.assert_not_called()

    def test_detect_false_install_engram_flag_installs_and_deposits(self):
        """GIVEN detect_engram=False y --install-engram WHEN run()
        THEN install_engram es llamado, luego deposit, retorna EXIT_OK."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(False, {})), \
             patch.object(installer, "install_engram", return_value=(True, "ok")), \
             patch.object(installer, "install_assets", return_value={"skills_deposited": 6,
                                                                      "shared_deposited": 3,
                                                                      "agents_deposited": 6,
                                                                      "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args(install_engram=True))

        assert result == installer.EXIT_OK

    def test_detect_false_prompt_n_returns_aborted(self):
        """GIVEN detect_engram=False y usuario responde N WHEN run()
        THEN retorna EXIT_ABORTED."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(False, {})), \
             patch.object(installer, "prompt_user_yn", return_value="n"), \
             patch("builtins.print"):
            result = installer.run(self._make_args())

        assert result == installer.EXIT_ABORTED

    def test_detect_false_prompt_y_installs_and_deposits(self):
        """GIVEN detect_engram=False y usuario responde Y WHEN run()
        THEN install_engram y install_assets se llaman, retorna EXIT_OK."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(False, {})), \
             patch.object(installer, "prompt_user_yn", return_value="y"), \
             patch.object(installer, "install_engram", return_value=(True, "ok")), \
             patch.object(installer, "install_assets", return_value={"skills_deposited": 6,
                                                                      "shared_deposited": 3,
                                                                      "agents_deposited": 6,
                                                                      "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args())

        assert result == installer.EXIT_OK

    def test_install_engram_failure_returns_engram_failed_code(self):
        """GIVEN install_engram retorna (False, msg) WHEN run()
        THEN retorna EXIT_ENGRAM_INSTALL_FAILED."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(False, {})), \
             patch.object(installer, "install_engram", return_value=(False, "Download failed")), \
             patch("builtins.print"), \
             patch("sys.stderr"):
            result = installer.run(self._make_args(install_engram=True))

        assert result == installer.EXIT_ENGRAM_INSTALL_FAILED

    def test_install_assets_failure_returns_deposit_failed_code(self):
        """GIVEN install_assets lanza excepción WHEN run()
        THEN retorna EXIT_DEPOSIT_FAILED."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(True, {})), \
             patch.object(installer, "install_assets", side_effect=SystemExit(installer.EXIT_DEPOSIT_FAILED)), \
             patch("builtins.print"):
            with pytest.raises(SystemExit) as exc:
                installer.run(self._make_args())
            assert exc.value.code == installer.EXIT_DEPOSIT_FAILED

    def test_install_engram_flag_wins_over_skip_check(self):
        """GIVEN ambos --install-engram y --skip-engram-check WHEN run()
        THEN --install-engram tiene precedencia y el install se ejecuta."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(False, {})), \
             patch.object(installer, "install_engram", return_value=(True, "ok")) as mock_install, \
             patch.object(installer, "install_assets", return_value={"skills_deposited": 6,
                                                                      "shared_deposited": 3,
                                                                      "agents_deposited": 6,
                                                                      "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args(install_engram=True, skip_engram_check=True))

        assert result == installer.EXIT_OK
        mock_install.assert_called_once()


class TestRunAdditional:
    """Tests adicionales de run() para cobertura de branches (T14)."""

    def _make_args(self, install_engram=False, skip_engram_check=False):
        import argparse
        return argparse.Namespace(
            install_engram=install_engram,
            skip_engram_check=skip_engram_check,
        )

    def test_detected_with_install_engram_flag_logs_and_skips_reinstall(self):
        """GIVEN detect_engram retorna True Y --install-engram flag WHEN run()
        THEN imprime 'ya detectado' y NO llama install_engram (REQ-FLAGS-03)."""
        from forge import installer

        with patch.object(installer, "detect_engram",
                          return_value=(True, {"mcp_json": "/usr/bin/engram"})), \
             patch.object(installer, "install_engram") as mock_install, \
             patch.object(installer, "install_assets", return_value={
                 "skills_deposited": 6, "shared_deposited": 3,
                 "agents_deposited": 6, "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"), \
             patch("builtins.print") as mock_print:
            result = installer.run(self._make_args(install_engram=True))

        assert result == installer.EXIT_OK
        mock_install.assert_not_called()
        # Verify the "ya detectado" message was printed
        printed_msgs = [str(c) for c in mock_print.call_args_list]
        assert any("ya detectado" in m for m in printed_msgs)

    def test_prompt_y_install_fails_returns_engram_failed(self):
        """GIVEN detect=False, prompt Y, install_engram falla WHEN run()
        THEN retorna EXIT_ENGRAM_INSTALL_FAILED."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(False, {})), \
             patch.object(installer, "prompt_user_yn", return_value="y"), \
             patch.object(installer, "install_engram", return_value=(False, "net error")), \
             patch("sys.stderr"):
            result = installer.run(self._make_args())

        assert result == installer.EXIT_ENGRAM_INSTALL_FAILED


class TestInstallEngramEdgeCases:
    """Casos edge de install_engram() para cobertura. T14."""

    def test_platform_unsupported_returns_false(self, monkeypatch):
        """GIVEN _detect_platform lanza SystemExit WHEN install_engram()
        THEN retorna (False, mensaje)."""
        from forge import installer

        with patch.object(installer, "_detect_platform",
                          side_effect=SystemExit(installer.EXIT_PLATFORM_UNSUPPORTED)):
            ok, msg = installer.install_engram()

        assert ok is False
        assert isinstance(msg, str)

    def test_api_failure_returns_false(self, monkeypatch):
        """GIVEN urllib.request.urlopen lanza URLError WHEN install_engram()
        THEN retorna (False, mensaje de error)."""
        import urllib.error

        from forge import installer

        with patch.object(installer, "_detect_platform", return_value=("linux", "amd64")), \
             patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("connection refused")):
            ok, msg = installer.install_engram()

        assert ok is False
        assert "No se pudo obtener" in msg

    def test_asset_not_found_returns_false(self, monkeypatch):
        """GIVEN la release no tiene asset para la plataforma WHEN install_engram()
        THEN retorna (False, mensaje con assets disponibles)."""
        from forge import installer

        api_response = MagicMock()
        api_response.read.return_value = json.dumps({
            "assets": [
                {"name": "engram_1.16.1_other_platform.tar.gz",
                 "browser_download_url": "https://example.com/other.tar.gz"}
            ]
        }).encode()
        api_response.__enter__ = lambda s: s
        api_response.__exit__ = MagicMock(return_value=False)

        with patch.object(installer, "_detect_platform", return_value=("linux", "amd64")), \
             patch("urllib.request.urlopen", return_value=api_response):
            ok, msg = installer.install_engram()

        assert ok is False
        assert "no encontrado" in msg.lower() or "Asset" in msg


class TestInjectFrontmatterEdgeCases:
    """Edge cases adicionales de inject_no_invoke_frontmatter. T14."""

    def test_frontmatter_with_non_dict_yaml_gets_prepended(self):
        """GIVEN frontmatter YAML que no es dict (e.g. lista) WHEN inject
        THEN trata como malformado y prepende frontmatter nuevo."""
        from forge.installer import inject_no_invoke_frontmatter
        # YAML list as frontmatter — non-standard but test the branch
        content = "---\n- item1\n- item2\n---\n\n# Body\n"
        result = inject_no_invoke_frontmatter(content)
        assert result.startswith("---\n")
        fm_raw = result[4:result.index("\n---\n", 4)]
        fm = yaml.safe_load(fm_raw)
        assert fm.get("disable-model-invocation") is True


class TestInstallAssetsEdgeCases:
    """Casos edge de install_assets para cobertura. T14."""

    def test_share_root_missing_raises_system_exit(self, tmp_path, monkeypatch):
        """GIVEN share root no existe WHEN install_assets()
        THEN lanza SystemExit(EXIT_DEPOSIT_FAILED)."""
        from forge import installer

        monkeypatch.setattr(installer, "get_share_root", lambda: tmp_path / "nonexistent")
        monkeypatch.setattr(installer, "CLAUDE_HOME", tmp_path / ".claude")

        with pytest.raises(SystemExit) as exc:
            installer.install_assets()
        assert exc.value.code == installer.EXIT_DEPOSIT_FAILED

    def test_missing_agents_dir_returns_zero_agents(self, tmp_path, monkeypatch):
        """GIVEN share/agents/ no existe WHEN install_assets()
        THEN agents_deposited == 0 sin error."""
        from forge import installer

        share = tmp_path / "share" / "forge"
        skills_dir = share / "skills"
        skills_dir.mkdir(parents=True)
        # No agents dir
        claude_home = tmp_path / ".claude"

        monkeypatch.setattr(installer, "get_share_root", lambda: share)
        monkeypatch.setattr(installer, "CLAUDE_HOME", claude_home)

        manifest = installer.install_assets()
        assert manifest["agents_deposited"] == 0


class TestPromptUserYn:
    """Verifica prompt_user_yn() — input handling. T12."""

    def test_y_returns_y(self):
        """GIVEN input 'y' WHEN prompt_user_yn() THEN retorna 'y'."""
        from forge.installer import prompt_user_yn
        with patch("builtins.input", return_value="y"):
            assert prompt_user_yn() == "y"

    def test_yes_case_insensitive_returns_y(self):
        """GIVEN input 'YES' WHEN prompt_user_yn() THEN retorna 'y'."""
        from forge.installer import prompt_user_yn
        with patch("builtins.input", return_value="YES"):
            assert prompt_user_yn() == "y"

    def test_no_returns_n(self):
        """GIVEN input 'n' WHEN prompt_user_yn() THEN retorna 'n'."""
        from forge.installer import prompt_user_yn
        with patch("builtins.input", return_value="n"):
            assert prompt_user_yn() == "n"

    def test_empty_returns_n(self):
        """GIVEN input '' WHEN prompt_user_yn() THEN retorna 'n' (default N)."""
        from forge.installer import prompt_user_yn
        with patch("builtins.input", return_value=""):
            assert prompt_user_yn() == "n"

    def test_arbitrary_string_returns_n(self):
        """GIVEN input 'maybe' WHEN prompt_user_yn() THEN retorna 'n'."""
        from forge.installer import prompt_user_yn
        with patch("builtins.input", return_value="maybe"):
            assert prompt_user_yn() == "n"


# ---------------------------------------------------------------------------
# TestPrintReport — PRD §4.A.2 (latent activation message)
# ---------------------------------------------------------------------------


class TestPrintReport:
    """Tests for print_report — PRD §4.A.2 (latent activation message)."""

    def _minimal_report(self) -> dict:
        """Helper: build a minimal report dict that exercises the function
        without triggering optional branches (no warnings, engram via mcp_json)."""
        return {
            "engram": {"mcp_json": "/fake/path/engram"},
            "assets": {
                "skills_deposited": 6,
                "shared_deposited": 3,
                "agents_deposited": 6,
                "warnings": [],
            },
        }

    def test_shows_latent_activation_anchor(self, capsys):
        """Output MUST contain the 'activates by context' anchor from
        POST_INSTALL_MESSAGE."""
        from forge.installer import print_report
        print_report(self._minimal_report())
        captured = capsys.readouterr()
        assert "se activa solo según el contexto" in captured.out

    def test_shows_skills_are_optional_anchor(self, capsys):
        """Output MUST contain the 'no need to know them' anchor."""
        from forge.installer import print_report
        print_report(self._minimal_report())
        captured = capsys.readouterr()
        assert "no necesitás conocerlas" in captured.out

    def test_does_not_mention_legacy_next_step(self, capsys):
        """Output MUST NOT contain the old 'Próximo paso: /fg-setup' line.
        Regression guard for PRD DoD #2."""
        from forge.installer import print_report
        print_report(self._minimal_report())
        captured = capsys.readouterr()
        assert "Próximo paso: /fg-setup" not in captured.out

    def test_post_install_message_constant_is_exported(self):
        """The module-level constant exists and contains both anchors.
        Validates the constants-as-copy contract (importable by tests and tooling)."""
        from forge.installer import POST_INSTALL_MESSAGE
        assert "se activa solo según el contexto" in POST_INSTALL_MESSAGE
        assert "no necesitás conocerlas" in POST_INSTALL_MESSAGE


# ---------------------------------------------------------------------------
# TestInjectOrchestratorRule — 4 TDD cycles (PRD A.3 scenarios)
# ---------------------------------------------------------------------------


class TestInjectOrchestratorRule:
    """Tests for inject_orchestrator_rule() — 4 scenarios from PRD A.3."""

    @pytest.fixture
    def fake_home(self, tmp_path, monkeypatch):
        """Isolate CLAUDE_HOME to tmp_path. Returns the fake claude home dir."""
        from forge import installer
        fake_claude = tmp_path / ".claude"
        monkeypatch.setattr(installer, "CLAUDE_HOME", fake_claude)
        return fake_claude

    @pytest.fixture
    def fake_template(self, tmp_path, monkeypatch):
        """Provide a fake template via monkeypatched get_share_root."""
        from forge import installer
        share = tmp_path / "share"
        templates = share / "templates"
        templates.mkdir(parents=True)
        (templates / "orchestrator-rule.md").write_text(
            "<!-- forge:orchestrator -->\nTEMPLATE BODY\n<!-- /forge:orchestrator -->\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(installer, "get_share_root", lambda: share)
        return templates / "orchestrator-rule.md"

    def test_first_time_creates_file(self, fake_home, fake_template):
        """GIVEN ~/.claude/ does not exist AND no CLAUDE.md
        WHEN inject_orchestrator_rule() is called
        THEN returns 'created', CLAUDE.md is created with template content,
        and a second call returns 'replaced' (idempotency invariant)."""
        from forge.installer import inject_orchestrator_rule

        result = inject_orchestrator_rule()

        assert result == "created"
        claude_md = fake_home / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text(encoding="utf-8")
        assert content == "<!-- forge:orchestrator -->\nTEMPLATE BODY\n<!-- /forge:orchestrator -->\n"

        # Idempotency invariant: second call must return 'replaced', not 'created'
        result2 = inject_orchestrator_rule()
        assert result2 == "replaced"

    def test_appends_to_existing_without_block(self, fake_home, fake_template):
        """GIVEN CLAUDE.md exists with content but NO forge markers
        WHEN inject_orchestrator_rule() is called
        THEN returns 'appended', original content preserved, template appended,
        blank-line separator present, and template appears exactly once."""
        from forge.installer import inject_orchestrator_rule

        fake_home.mkdir(parents=True)
        original = "# Gentle AI Rules\n\nSome instructions.\n"
        (fake_home / "CLAUDE.md").write_text(original, encoding="utf-8")

        result = inject_orchestrator_rule()

        assert result == "appended"
        content = (fake_home / "CLAUDE.md").read_text(encoding="utf-8")

        # Original content byte-for-byte unchanged at start (R-INJECT-05)
        assert content.startswith(original)

        # Template block appears at the end
        template_block = "<!-- forge:orchestrator -->\nTEMPLATE BODY\n<!-- /forge:orchestrator -->\n"
        assert content.endswith(template_block)

        # Blank-line separator present between original and block (EC-05)
        assert original + "\n" + template_block == content

        # Template block appears exactly once
        assert content.count("<!-- forge:orchestrator -->") == 1

    def test_appends_separator_when_no_trailing_newline(self, fake_home, fake_template):
        """GIVEN CLAUDE.md exists ending WITHOUT trailing newline (EC-05 edge)
        WHEN inject_orchestrator_rule() is called
        THEN a double-newline separator ensures blank line before forge block."""
        from forge.installer import inject_orchestrator_rule

        fake_home.mkdir(parents=True)
        # File ends WITHOUT trailing newline
        original_no_nl = "# Rules without trailing newline"
        (fake_home / "CLAUDE.md").write_text(original_no_nl, encoding="utf-8")

        result = inject_orchestrator_rule()

        assert result == "appended"
        content = (fake_home / "CLAUDE.md").read_text(encoding="utf-8")
        # Double-newline separator must be present (sep = "\n\n" when no trailing \n)
        assert "\n\n<!-- forge:orchestrator -->" in content
        assert content.count("<!-- forge:orchestrator -->") == 1

    def test_replaces_existing_block_idempotent(self, fake_home, fake_template):
        """GIVEN CLAUDE.md contains a stale forge block (different body)
        WHEN inject_orchestrator_rule() is called once then again
        THEN first call returns 'replaced' with new body,
        second call returns 'replaced' with byte-identical content (idempotent),
        and exactly ONE opening marker exists in the final file."""
        from forge.installer import inject_orchestrator_rule

        fake_home.mkdir(parents=True)
        stale = (
            "<!-- forge:orchestrator -->\nOLD CONTENT\n<!-- /forge:orchestrator -->\n"
        )
        (fake_home / "CLAUDE.md").write_text(stale, encoding="utf-8")

        result1 = inject_orchestrator_rule()

        assert result1 == "replaced"
        content_after_first = (fake_home / "CLAUDE.md").read_text(encoding="utf-8")
        assert "TEMPLATE BODY" in content_after_first
        assert "OLD CONTENT" not in content_after_first

        # Idempotency: second call must return 'replaced' and content identical
        result2 = inject_orchestrator_rule()
        content_after_second = (fake_home / "CLAUDE.md").read_text(encoding="utf-8")
        assert result2 == "replaced"
        assert content_after_second == content_after_first

        # Exactly ONE open marker in final file (NFR-01)
        assert content_after_second.count("<!-- forge:orchestrator -->") == 1

    def test_replaces_preserves_prefix_and_suffix(self, fake_home, fake_template):
        """TRIANGULATE: prefix and suffix content around the forge block are unchanged."""
        from forge.installer import inject_orchestrator_rule

        fake_home.mkdir(parents=True)
        prefix = "prefix content\n"
        suffix = "suffix content\n"
        initial = (
            prefix
            + "<!-- forge:orchestrator -->\nOLD CONTENT\n<!-- /forge:orchestrator -->\n"
            + suffix
        )
        (fake_home / "CLAUDE.md").write_text(initial, encoding="utf-8")

        result = inject_orchestrator_rule()

        assert result == "replaced"
        content = (fake_home / "CLAUDE.md").read_text(encoding="utf-8")
        assert content.startswith(prefix)
        assert content.endswith(suffix)
        assert "TEMPLATE BODY" in content
        assert content.count("<!-- forge:orchestrator -->") == 1

    def test_preserves_gentle_ai_block(self, fake_home, fake_template):
        """GIVEN CLAUDE.md contains a Gentle AI block AND a stale forge block
        WHEN inject_orchestrator_rule() is called
        THEN returns 'replaced', Gentle AI block is byte-for-byte unchanged,
        only the forge block body is updated, and no other content is modified."""
        from forge.installer import inject_orchestrator_rule

        fake_home.mkdir(parents=True)
        gentle_ai_block = (
            "<!-- gentle-ai:persona -->\n"
            "You are a senior architect.\n"
            "<!-- /gentle-ai:persona -->\n"
        )
        forge_block_stale = (
            "<!-- forge:orchestrator -->\n"
            "OLD FORGE CONTENT\n"
            "<!-- /forge:orchestrator -->\n"
        )
        after_content = "\n## After forge block\n\nMore user content.\n"
        initial = gentle_ai_block + "\n" + forge_block_stale + after_content
        (fake_home / "CLAUDE.md").write_text(initial, encoding="utf-8")

        result = inject_orchestrator_rule()

        assert result == "replaced"
        content = (fake_home / "CLAUDE.md").read_text(encoding="utf-8")

        # Gentle AI block is byte-for-byte unchanged (R-INJECT-05)
        assert gentle_ai_block in content
        # Specifically verify the gentle-ai:persona string is unchanged (R-INJECT-05 test oracle)
        assert "gentle-ai:persona" in content
        assert "You are a senior architect." in content

        # Forge block is updated to new template
        assert "TEMPLATE BODY" in content
        assert "OLD FORGE CONTENT" not in content

        # Content after forge block (suffix) is byte-for-byte unchanged
        assert content.endswith(after_content)

        # Only the forge body changed — no duplication
        assert content.count("<!-- forge:orchestrator -->") == 1


# ---------------------------------------------------------------------------
# PR-A: TestDetectCodegraph — T-01 RED / T-02 GREEN
# ---------------------------------------------------------------------------


class TestDetectCodegraph:
    """Verifica detect_codegraph() — indicador único: shutil.which. PR-A T-01/T-02."""

    def test_which_returns_path_gives_true(self, monkeypatch):
        """GIVEN shutil.which('codegraph') retorna una ruta válida
        WHEN detect_codegraph() THEN retorna (True, {'which': ruta})."""
        from forge import installer

        monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/codegraph" if name == "codegraph" else None)

        found, info = installer.detect_codegraph()
        assert found is True
        assert info.get("which") == "/usr/local/bin/codegraph"

    def test_which_returns_none_gives_false(self, monkeypatch):
        """GIVEN shutil.which('codegraph') retorna None
        WHEN detect_codegraph() THEN retorna (False, {})."""
        from forge import installer

        monkeypatch.setattr("shutil.which", lambda _: None)

        found, info = installer.detect_codegraph()
        assert found is False
        assert info == {}

    def test_which_oserror_gives_false(self, monkeypatch):
        """GIVEN shutil.which lanza OSError (triangulación T-07)
        WHEN detect_codegraph() THEN captura la excepción y retorna (False, {})."""
        from forge import installer

        def raising_which(_name):
            raise OSError("permiso denegado")

        monkeypatch.setattr("shutil.which", raising_which)

        found, info = installer.detect_codegraph()
        assert found is False
        assert info == {}

    def test_does_not_write_filesystem(self, tmp_path, monkeypatch):
        """GIVEN detect_codegraph() WHEN se llama THEN no escribe ni modifica el filesystem."""
        from forge import installer

        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/codegraph")
        # Verificamos que tmp_path sigue vacío después de la llamada
        before = list(tmp_path.iterdir())
        installer.detect_codegraph()
        after = list(tmp_path.iterdir())
        assert before == after

    def test_does_not_make_subprocess_calls(self, monkeypatch):
        """GIVEN detect_codegraph() WHEN se llama THEN no invoca subprocess (pureza)."""
        import subprocess

        from forge import installer

        monkeypatch.setattr("shutil.which", lambda _: None)

        called = []

        original_run = subprocess.run

        def spy_run(*args, **kwargs):
            called.append(args)
            return original_run(*args, **kwargs)

        monkeypatch.setattr(subprocess, "run", spy_run)
        installer.detect_codegraph()
        assert called == [], "detect_codegraph no debe invocar subprocess"


# ---------------------------------------------------------------------------
# PR-A: TestCodegraphAssetName — T-03 RED / T-04 GREEN
# ---------------------------------------------------------------------------


class TestCodegraphAssetName:
    """Verifica _codegraph_asset_name() — mapa de 6 combinaciones reales. PR-A T-03/T-04."""

    @pytest.mark.parametrize("os_tok, arch_tok, expected", [
        ("darwin", "arm64", "codegraph-darwin-arm64.tar.gz"),
        ("darwin", "x64",   "codegraph-darwin-x64.tar.gz"),
        ("linux",  "x64",   "codegraph-linux-x64.tar.gz"),
        ("linux",  "arm64", "codegraph-linux-arm64.tar.gz"),
        ("win32",  "x64",   "codegraph-win32-x64.zip"),
        ("win32",  "arm64", "codegraph-win32-arm64.zip"),
    ])
    def test_asset_name_known_platforms(self, os_tok, arch_tok, expected):
        """GIVEN una combinación soportada de (os_tok, arch_tok)
        WHEN _codegraph_asset_name(os_tok, arch_tok) THEN retorna el nombre correcto del asset."""
        from forge import installer

        result = installer._codegraph_asset_name(os_tok, arch_tok)
        assert result == expected

    def test_unsupported_platform_raises(self):
        """GIVEN una combinación no soportada WHEN _codegraph_asset_name() THEN lanza ValueError."""
        from forge import installer

        with pytest.raises((ValueError, SystemExit)):
            installer._codegraph_asset_name("freebsd", "mips")

    def test_uses_win32_not_windows_token(self):
        """GIVEN la plataforma Windows WHEN _codegraph_asset_name()
        THEN usa 'win32' como token OS (distinto al 'windows' de engram)."""
        from forge import installer

        result = installer._codegraph_asset_name("win32", "x64")
        assert "win32" in result
        assert "windows" not in result

    def test_uses_x64_not_amd64_token(self):
        """GIVEN arch x64 WHEN _codegraph_asset_name()
        THEN usa 'x64' como token arch (distinto al 'amd64' de engram)."""
        from forge import installer

        result = installer._codegraph_asset_name("linux", "x64")
        assert "x64" in result
        assert "amd64" not in result

    def test_win32_uses_zip_extension(self):
        """GIVEN plataforma win32 WHEN _codegraph_asset_name() THEN usa extensión .zip."""
        from forge import installer

        result = installer._codegraph_asset_name("win32", "x64")
        assert result.endswith(".zip")

    def test_unix_uses_tar_gz_extension(self):
        """GIVEN plataformas darwin/linux WHEN _codegraph_asset_name() THEN usa extensión .tar.gz."""
        from forge import installer

        assert installer._codegraph_asset_name("darwin", "arm64").endswith(".tar.gz")
        assert installer._codegraph_asset_name("linux", "x64").endswith(".tar.gz")


# ---------------------------------------------------------------------------
# PR-A: TestVerifySha256 — T-05 RED / T-06 GREEN
# ---------------------------------------------------------------------------


class TestVerifySha256:
    """Verifica _verify_sha256() — integridad SHA256 contra contenido de SHA256SUMS. PR-A T-05/T-06."""

    def _build_sha256sums(self, file_path: Path, asset_name: str) -> str:
        """Calcula el SHA256 real de file_path y retorna una línea SHA256SUMS válida."""
        import hashlib
        digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
        return f"{digest}  {asset_name}\n"

    def test_correct_hash_returns_true(self, tmp_path):
        """GIVEN un archivo y su SHA256SUMS correcto WHEN _verify_sha256() THEN retorna (True, 'ok')."""
        from forge import installer

        asset_name = "codegraph-linux-x64.tar.gz"
        fixture = tmp_path / asset_name
        fixture.write_bytes(b"contenido de prueba para sha256")

        sha256sums = self._build_sha256sums(fixture, asset_name)

        ok, msg = installer._verify_sha256(fixture, sha256sums, asset_name)
        assert ok is True
        assert msg == "ok"

    def test_wrong_hash_returns_false(self, tmp_path):
        """GIVEN un hash incorrecto en SHA256SUMS WHEN _verify_sha256() THEN retorna (False, mensaje)."""
        from forge import installer

        asset_name = "codegraph-darwin-arm64.tar.gz"
        fixture = tmp_path / asset_name
        fixture.write_bytes(b"contenido real")

        sha256sums = f"{'a' * 64}  {asset_name}\n"

        ok, msg = installer._verify_sha256(fixture, sha256sums, asset_name)
        assert ok is False
        assert "mismatch" in msg.lower() or "hash" in msg.lower()

    def test_asset_not_found_in_sums_returns_false(self, tmp_path):
        """GIVEN el asset_name no está en SHA256SUMS WHEN _verify_sha256() THEN retorna (False, msg)."""
        from forge import installer

        asset_name = "codegraph-linux-x64.tar.gz"
        fixture = tmp_path / asset_name
        fixture.write_bytes(b"datos")

        sha256sums = f"{'b' * 64}  codegraph-darwin-arm64.tar.gz\n"

        ok, msg = installer._verify_sha256(fixture, sha256sums, asset_name)
        assert ok is False
        assert "not found" in msg.lower() or "no encontrado" in msg.lower()

    def test_empty_sha256sums_returns_false(self, tmp_path):
        """GIVEN SHA256SUMS vacío WHEN _verify_sha256() THEN retorna (False, msg)."""
        from forge import installer

        asset_name = "codegraph-win32-x64.zip"
        fixture = tmp_path / asset_name
        fixture.write_bytes(b"datos")

        ok, msg = installer._verify_sha256(fixture, "", asset_name)
        assert ok is False

    def test_two_space_separator_format(self, tmp_path):
        """GIVEN formato SHA256SUMS con dos espacios (estándar) WHEN _verify_sha256()
        THEN parsea correctamente la línea y retorna True — formato real verificado."""
        import hashlib

        from forge import installer

        asset_name = "codegraph-linux-arm64.tar.gz"
        fixture = tmp_path / asset_name
        content = b"binario arm64 de prueba"
        fixture.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()

        # Formato exacto: <hash><DOS_ESPACIOS><nombre>
        sha256sums = f"{digest}  {asset_name}\n"

        ok, msg = installer._verify_sha256(fixture, sha256sums, asset_name)
        assert ok is True

    def test_empty_file_hash_mismatch(self, tmp_path):
        """GIVEN archivo vacío con hash de contenido no-vacío WHEN _verify_sha256() THEN retorna False."""
        import hashlib

        from forge import installer

        asset_name = "codegraph-darwin-x64.tar.gz"
        fixture = tmp_path / asset_name
        fixture.write_bytes(b"")  # archivo vacío

        # Hash de contenido no-vacío → no coincide con hash del archivo vacío
        wrong_hash = hashlib.sha256(b"contenido no vacio").hexdigest()
        sha256sums = f"{wrong_hash}  {asset_name}\n"

        ok, _ = installer._verify_sha256(fixture, sha256sums, asset_name)
        assert ok is False


# ---------------------------------------------------------------------------
# PR-B: TestInstallCodegraph — T-08 RED / T-09 GREEN
# ---------------------------------------------------------------------------


class TestInstallCodegraph:
    """Verifica install_codegraph() — happy path, fallo de red, plataforma inválida. PR-B T-08/T-09."""

    def _make_api_response(self, asset_name: str, download_url: str) -> MagicMock:
        """Construye un mock de urllib.request.urlopen con release metadata."""
        resp = MagicMock()
        resp.read.return_value = json.dumps({
            "tag_name": "v0.3.0",
            "assets": [
                {"name": asset_name, "browser_download_url": download_url},
                {"name": "SHA256SUMS", "browser_download_url": "https://example.com/SHA256SUMS"},
            ],
        }).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def _make_sha256sums_response(self, asset_name: str, tmp_path: Path) -> tuple[MagicMock, str]:
        """Crea un fixture de archivo y retorna su SHA256SUMS content correcto."""
        import hashlib
        content = b"fake codegraph binary content"
        digest = hashlib.sha256(content).hexdigest()
        sha256sums_text = f"{digest}  {asset_name}\n"
        sha256sums_resp = MagicMock()
        sha256sums_resp.read.return_value = sha256sums_text.encode()
        sha256sums_resp.__enter__ = lambda s: s
        sha256sums_resp.__exit__ = MagicMock(return_value=False)
        return sha256sums_resp, content

    def test_happy_path_unix_returns_true(self, tmp_path, monkeypatch):
        """GIVEN plataforma linux/x64, API responde, descarga y SHA256 OK
        WHEN install_codegraph() THEN retorna (True, mensaje con ruta del binario)."""
        import hashlib

        from forge import installer

        asset_name = "codegraph-linux-x64.tar.gz"
        binary_content = b"fake binary"
        sha256 = hashlib.sha256(binary_content).hexdigest()
        sha256sums_text = f"{sha256}  {asset_name}\n"

        # Redirigir bin dir a tmp_path
        monkeypatch.setattr(installer, "CODEGRAPH_BIN_DIR_UNIX", tmp_path / "bin")
        monkeypatch.setattr(installer, "CODEGRAPH_BIN_DIR_WIN", tmp_path / "bin")

        api_resp = MagicMock()
        api_resp.read.return_value = json.dumps({
            "tag_name": "v0.3.0",
            "assets": [
                {"name": asset_name, "browser_download_url": "https://example.com/cg.tar.gz"},
                {"name": "SHA256SUMS", "browser_download_url": "https://example.com/SHA256SUMS"},
            ],
        }).encode()
        api_resp.__enter__ = lambda s: s
        api_resp.__exit__ = MagicMock(return_value=False)

        sha256sums_resp = MagicMock()
        sha256sums_resp.read.return_value = sha256sums_text.encode()
        sha256sums_resp.__enter__ = lambda s: s
        sha256sums_resp.__exit__ = MagicMock(return_value=False)

        # Mock tarfile: extraer binario falso
        import tarfile
        mock_member = MagicMock(spec=tarfile.TarInfo)
        mock_member.name = "codegraph-linux-x64/codegraph"
        mock_tf = MagicMock()
        mock_tf.__enter__ = lambda s: s
        mock_tf.__exit__ = MagicMock(return_value=False)
        mock_tf.getmembers.return_value = [mock_member]
        mock_tf.extract = MagicMock()

        def fake_download(url, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(binary_content)

        with patch.object(installer, "_detect_codegraph_platform", return_value=("linux", "x64")), \
             patch("urllib.request.urlopen", side_effect=[api_resp, sha256sums_resp]), \
             patch.object(installer, "_download_binary", side_effect=fake_download), \
             patch("tarfile.open", return_value=mock_tf), \
             patch("os.chmod"), \
             patch("os.unlink"), \
             patch.object(installer, "_xattr_cleanup_darwin"):
            ok, msg = installer.install_codegraph()

        assert ok is True
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_network_failure_returns_false(self, tmp_path, monkeypatch):
        """GIVEN urllib.request.urlopen lanza URLError WHEN install_codegraph()
        THEN retorna (False, mensaje de error) sin lanzar excepción."""
        import urllib.error

        from forge import installer

        monkeypatch.setattr(installer, "CODEGRAPH_BIN_DIR_UNIX", tmp_path / "bin")

        with patch.object(installer, "_detect_codegraph_platform", return_value=("linux", "x64")), \
             patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("sin red")):
            ok, msg = installer.install_codegraph()

        assert ok is False
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_unsupported_platform_returns_false(self, tmp_path, monkeypatch):
        """GIVEN _detect_codegraph_platform lanza SystemExit WHEN install_codegraph()
        THEN retorna (False, mensaje) sin propagar la excepción."""
        from forge import installer

        with patch.object(installer, "_detect_codegraph_platform",
                          side_effect=SystemExit(installer.EXIT_PLATFORM_UNSUPPORTED)):
            ok, msg = installer.install_codegraph()

        assert ok is False
        assert isinstance(msg, str)

    def test_sha256_mismatch_returns_false(self, tmp_path, monkeypatch):
        """GIVEN SHA256SUMS contiene hash incorrecto WHEN install_codegraph()
        THEN retorna (False, mensaje de verificación fallida)."""
        from forge import installer

        asset_name = "codegraph-linux-x64.tar.gz"
        binary_content = b"fake binary"

        monkeypatch.setattr(installer, "CODEGRAPH_BIN_DIR_UNIX", tmp_path / "bin")
        monkeypatch.setattr(installer, "CODEGRAPH_BIN_DIR_WIN", tmp_path / "bin")

        wrong_sha256 = "a" * 64
        sha256sums_text = f"{wrong_sha256}  {asset_name}\n"

        api_resp = MagicMock()
        api_resp.read.return_value = json.dumps({
            "tag_name": "v0.3.0",
            "assets": [
                {"name": asset_name, "browser_download_url": "https://example.com/cg.tar.gz"},
                {"name": "SHA256SUMS", "browser_download_url": "https://example.com/SHA256SUMS"},
            ],
        }).encode()
        api_resp.__enter__ = lambda s: s
        api_resp.__exit__ = MagicMock(return_value=False)

        sha256sums_resp = MagicMock()
        sha256sums_resp.read.return_value = sha256sums_text.encode()
        sha256sums_resp.__enter__ = lambda s: s
        sha256sums_resp.__exit__ = MagicMock(return_value=False)

        def fake_download(url, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(binary_content)

        with patch.object(installer, "_detect_codegraph_platform", return_value=("linux", "x64")), \
             patch("urllib.request.urlopen", side_effect=[api_resp, sha256sums_resp]), \
             patch.object(installer, "_download_binary", side_effect=fake_download), \
             patch("os.unlink"):
            ok, msg = installer.install_codegraph()

        assert ok is False
        assert isinstance(msg, str)

    def test_asset_not_found_in_release_returns_false(self, tmp_path, monkeypatch):
        """GIVEN la release no contiene el asset para la plataforma WHEN install_codegraph()
        THEN retorna (False, mensaje descriptivo)."""
        from forge import installer

        monkeypatch.setattr(installer, "CODEGRAPH_BIN_DIR_UNIX", tmp_path / "bin")

        api_resp = MagicMock()
        api_resp.read.return_value = json.dumps({
            "tag_name": "v0.3.0",
            "assets": [
                {"name": "codegraph-darwin-arm64.tar.gz",
                 "browser_download_url": "https://example.com/other.tar.gz"},
            ],
        }).encode()
        api_resp.__enter__ = lambda s: s
        api_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(installer, "_detect_codegraph_platform", return_value=("linux", "x64")), \
             patch("urllib.request.urlopen", return_value=api_resp):
            ok, msg = installer.install_codegraph()

        assert ok is False
        assert isinstance(msg, str)

    def test_happy_path_windows_returns_true(self, tmp_path, monkeypatch):
        """GIVEN plataforma win32/x64, descarga zip exitosa WHEN install_codegraph()
        THEN retorna (True, mensaje). Triangulación: comportamiento zip distinto a tar.gz."""
        import hashlib

        from forge import installer

        asset_name = "codegraph-win32-x64.zip"
        binary_content = b"fake windows binary"
        sha256 = hashlib.sha256(binary_content).hexdigest()
        sha256sums_text = f"{sha256}  {asset_name}\n"

        monkeypatch.setattr(installer, "CODEGRAPH_BIN_DIR_WIN", tmp_path / "bin")
        monkeypatch.setattr(installer, "CODEGRAPH_BIN_DIR_UNIX", tmp_path / "bin")

        api_resp = MagicMock()
        api_resp.read.return_value = json.dumps({
            "tag_name": "v0.3.0",
            "assets": [
                {"name": asset_name, "browser_download_url": "https://example.com/cg.zip"},
                {"name": "SHA256SUMS", "browser_download_url": "https://example.com/SHA256SUMS"},
            ],
        }).encode()
        api_resp.__enter__ = lambda s: s
        api_resp.__exit__ = MagicMock(return_value=False)

        sha256sums_resp = MagicMock()
        sha256sums_resp.read.return_value = sha256sums_text.encode()
        sha256sums_resp.__enter__ = lambda s: s
        sha256sums_resp.__exit__ = MagicMock(return_value=False)

        mock_zf = MagicMock()
        mock_zf.__enter__ = lambda s: s
        mock_zf.__exit__ = MagicMock(return_value=False)
        mock_zf.namelist.return_value = ["codegraph-win32-x64/codegraph.exe"]
        mock_src = MagicMock()
        mock_src.__enter__ = lambda s: s
        mock_src.__exit__ = MagicMock(return_value=False)
        mock_src.read.return_value = binary_content
        mock_zf.open.return_value = mock_src

        def fake_download(url, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(binary_content)

        with patch.object(installer, "_detect_codegraph_platform", return_value=("win32", "x64")), \
             patch("urllib.request.urlopen", side_effect=[api_resp, sha256sums_resp]), \
             patch.object(installer, "_download_binary", side_effect=fake_download), \
             patch("zipfile.ZipFile", return_value=mock_zf), \
             patch("os.unlink"):
            ok, msg = installer.install_codegraph()

        assert ok is True
        assert isinstance(msg, str)


# ---------------------------------------------------------------------------
# PR-B: TestDetectCodegraphPlatform — helper interno
# ---------------------------------------------------------------------------


class TestDetectCodegraphPlatform:
    """Verifica _detect_codegraph_platform() — mapeo a tokens de CodeGraph. PR-B."""

    def test_linux_x86_64_maps_to_linux_x64(self, monkeypatch):
        """GIVEN sys.platform='linux', machine='x86_64'
        WHEN _detect_codegraph_platform() THEN retorna ('linux', 'x64')."""
        from forge import installer
        monkeypatch.setattr("sys.platform", "linux")
        with patch("platform.machine", return_value="x86_64"):
            os_tok, arch_tok = installer._detect_codegraph_platform()
        assert os_tok == "linux"
        assert arch_tok == "x64"

    def test_darwin_arm64_maps_correctly(self, monkeypatch):
        """GIVEN sys.platform='darwin', machine='arm64'
        WHEN _detect_codegraph_platform() THEN retorna ('darwin', 'arm64')."""
        from forge import installer
        monkeypatch.setattr("sys.platform", "darwin")
        with patch("platform.machine", return_value="arm64"):
            os_tok, arch_tok = installer._detect_codegraph_platform()
        assert os_tok == "darwin"
        assert arch_tok == "arm64"

    def test_win32_amd64_maps_to_win32_x64(self, monkeypatch):
        """GIVEN sys.platform='win32', machine='AMD64'
        WHEN _detect_codegraph_platform() THEN retorna ('win32', 'x64')."""
        from forge import installer
        monkeypatch.setattr("sys.platform", "win32")
        with patch("platform.machine", return_value="AMD64"):
            os_tok, arch_tok = installer._detect_codegraph_platform()
        assert os_tok == "win32"
        assert arch_tok == "x64"

    def test_unsupported_platform_raises_system_exit(self, monkeypatch):
        """GIVEN plataforma no soportada WHEN _detect_codegraph_platform()
        THEN lanza SystemExit con EXIT_PLATFORM_UNSUPPORTED."""
        from forge import installer
        monkeypatch.setattr("sys.platform", "freebsd")
        with patch("platform.machine", return_value="x86_64"), \
             pytest.raises(SystemExit) as exc:
            installer._detect_codegraph_platform()
        assert exc.value.code == installer.EXIT_PLATFORM_UNSUPPORTED


# ---------------------------------------------------------------------------
# PR-B: TestRegisterCodegraphMcp — T-10 RED / T-11 GREEN
# ---------------------------------------------------------------------------


class TestRegisterCodegraphMcp:
    """Verifica register_codegraph_mcp() — merge idempotente en ~/.claude.json. PR-B T-10/T-11."""

    def test_creates_mcp_block_when_file_missing(self, tmp_path, monkeypatch):
        """GIVEN ~/.claude.json no existe WHEN register_codegraph_mcp()
        THEN crea el archivo con mcpServers.codegraph y retorna 'created'."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)

        status = installer.register_codegraph_mcp()

        assert status == "created"
        assert claude_json.exists()
        data = json.loads(claude_json.read_text(encoding="utf-8"))
        assert "mcpServers" in data
        assert "codegraph" in data["mcpServers"]
        cg = data["mcpServers"]["codegraph"]
        assert cg["type"] == "stdio"
        assert cg["command"] == "codegraph"

    def test_merges_without_overwriting_existing_config(self, tmp_path, monkeypatch):
        """GIVEN ~/.claude.json con config previa del dev WHEN register_codegraph_mcp()
        THEN preserva las claves existentes y agrega mcpServers.codegraph."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        existing_config = {
            "theme": "dark",
            "mcpServers": {
                "engram": {
                    "type": "stdio",
                    "command": "/home/user/.engram/bin/engram",
                    "args": ["mcp", "--tools=agent"],
                }
            },
        }
        claude_json.write_text(
            json.dumps(existing_config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)

        status = installer.register_codegraph_mcp()

        assert status in ("created", "merged")
        data = json.loads(claude_json.read_text(encoding="utf-8"))
        # Config existente preservada
        assert data.get("theme") == "dark"
        assert "engram" in data["mcpServers"], "El bloque engram existente debe preservarse"
        # CodeGraph agregado
        assert "codegraph" in data["mcpServers"]

    def test_idempotent_second_call_returns_present(self, tmp_path, monkeypatch):
        """GIVEN register_codegraph_mcp() ya fue llamado WHEN se llama de nuevo
        THEN retorna 'present' y NO modifica el archivo."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)

        installer.register_codegraph_mcp()
        content_after_first = claude_json.read_text(encoding="utf-8")

        status2 = installer.register_codegraph_mcp()

        assert status2 == "present"
        content_after_second = claude_json.read_text(encoding="utf-8")
        assert content_after_first == content_after_second

    def test_creates_backup_before_writing(self, tmp_path, monkeypatch):
        """GIVEN ~/.claude.json con config existente WHEN register_codegraph_mcp()
        THEN crea backup .claude.json.forge-bak con el contenido original."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        original_content = json.dumps({"theme": "light"}, indent=2)
        claude_json.write_text(original_content, encoding="utf-8")
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)

        installer.register_codegraph_mcp()

        backup = tmp_path / ".claude.json.forge-bak"
        assert backup.exists(), "Debe existir el archivo de backup .claude.json.forge-bak"
        assert backup.read_text(encoding="utf-8") == original_content

    def test_handles_corrupted_json_gracefully(self, tmp_path, monkeypatch):
        """GIVEN ~/.claude.json existe pero contiene JSON inválido WHEN register_codegraph_mcp()
        THEN trata el archivo como vacío y retorna 'created' o 'merged' sin lanzar excepción."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        claude_json.write_text("{ invalid json {{", encoding="utf-8")
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)

        # No debe lanzar excepción
        status = installer.register_codegraph_mcp()

        assert status in ("created", "merged")
        # El archivo resultante debe ser JSON válido
        data = json.loads(claude_json.read_text(encoding="utf-8"))
        assert "mcpServers" in data
        assert "codegraph" in data["mcpServers"]

    def test_codegraph_block_has_correct_schema(self, tmp_path, monkeypatch):
        """GIVEN registro exitoso WHEN se lee el bloque codegraph
        THEN tiene type=stdio, command=codegraph, args=[serve, --mcp]."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)

        installer.register_codegraph_mcp()

        data = json.loads(claude_json.read_text(encoding="utf-8"))
        cg = data["mcpServers"]["codegraph"]
        assert cg["type"] == "stdio"
        assert cg["command"] == "codegraph"
        assert "serve" in cg["args"]
        assert "--mcp" in cg["args"]


# ---------------------------------------------------------------------------
# PR-B: TestPromptCodegraphYn — T-12 RED / T-13 GREEN
# ---------------------------------------------------------------------------


class TestPromptCodegraphYn:
    """Verifica prompt_codegraph_yn() — y/N, default instalar, CI-safe. PR-B T-12/T-13."""

    def test_y_input_returns_y(self):
        """GIVEN input 'y' WHEN prompt_codegraph_yn() THEN retorna 'y'."""
        from forge.installer import prompt_codegraph_yn
        with patch("builtins.input", return_value="y"), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            assert prompt_codegraph_yn() == "y"

    def test_yes_input_returns_y(self):
        """GIVEN input 'yes' WHEN prompt_codegraph_yn() THEN retorna 'y'."""
        from forge.installer import prompt_codegraph_yn
        with patch("builtins.input", return_value="yes"), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            assert prompt_codegraph_yn() == "y"

    def test_empty_input_returns_y_as_default(self):
        """GIVEN input vacío (enter) WHEN prompt_codegraph_yn() THEN retorna 'y' (default instalar)."""
        from forge.installer import prompt_codegraph_yn
        with patch("builtins.input", return_value=""), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            assert prompt_codegraph_yn() == "y"

    def test_n_input_returns_n(self):
        """GIVEN input 'n' WHEN prompt_codegraph_yn() THEN retorna 'n'."""
        from forge.installer import prompt_codegraph_yn
        with patch("builtins.input", return_value="n"), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            assert prompt_codegraph_yn() == "n"

    def test_non_interactive_returns_y_without_hanging(self, monkeypatch):
        """GIVEN entorno no-interactivo (stdin no es tty) WHEN prompt_codegraph_yn()
        THEN retorna 'y' (instalar por defecto) sin llamar input()."""
        from forge.installer import prompt_codegraph_yn

        called = []
        monkeypatch.setattr("builtins.input", lambda _: called.append(True) or "")

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = prompt_codegraph_yn()

        assert result == "y"
        assert called == [], "input() no debe llamarse en entorno no-interactivo"


# ---------------------------------------------------------------------------
# PR-B: TestRunCodegraph — T-14 RED / T-15 GREEN
# ---------------------------------------------------------------------------


class TestRunCodegraph:
    """Verifica integración de CodeGraph en run() y print_report(). PR-B T-14/T-15."""

    def _make_args(
        self,
        install_engram=False,
        skip_engram_check=True,
        skip_codegraph=False,
        install_codegraph=False,
    ):
        import argparse
        return argparse.Namespace(
            install_engram=install_engram,
            skip_engram_check=skip_engram_check,
            skip_codegraph=skip_codegraph,
            install_codegraph=install_codegraph,
        )

    def test_codegraph_failure_does_not_change_exit_ok(self):
        """GIVEN install_codegraph() falla WHEN run() THEN retorna EXIT_OK (fallo graceful R-INST-05)."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(True, {"which": "/p"})), \
             patch.object(installer, "detect_codegraph", return_value=(False, {})), \
             patch.object(installer, "prompt_codegraph_yn", return_value="y"), \
             patch.object(installer, "install_codegraph", return_value=(False, "error de red")), \
             patch.object(installer, "register_codegraph_mcp", return_value="created"), \
             patch.object(installer, "install_assets", return_value={
                 "skills_deposited": 6, "shared_deposited": 3,
                 "agents_deposited": 6, "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args())

        assert result == installer.EXIT_OK

    def test_skip_codegraph_flag_skips_install(self):
        """GIVEN --skip-codegraph flag WHEN run() THEN install_codegraph NO es llamado."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(True, {"which": "/p"})), \
             patch.object(installer, "detect_codegraph", return_value=(False, {})), \
             patch.object(installer, "install_codegraph") as mock_install, \
             patch.object(installer, "install_assets", return_value={
                 "skills_deposited": 6, "shared_deposited": 3,
                 "agents_deposited": 6, "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args(skip_codegraph=True))

        assert result == installer.EXIT_OK
        mock_install.assert_not_called()

    def test_codegraph_already_detected_skips_install(self):
        """GIVEN detect_codegraph() retorna True WHEN run()
        THEN install_codegraph NO es llamado (idempotencia R-INST-02)."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(True, {"which": "/p"})), \
             patch.object(installer, "detect_codegraph", return_value=(True, {"which": "/usr/bin/codegraph"})), \
             patch.object(installer, "install_codegraph") as mock_install, \
             patch.object(installer, "register_codegraph_mcp", return_value="present"), \
             patch.object(installer, "install_assets", return_value={
                 "skills_deposited": 6, "shared_deposited": 3,
                 "agents_deposited": 6, "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args())

        assert result == installer.EXIT_OK
        mock_install.assert_not_called()

    def test_install_codegraph_flag_installs_without_prompt(self):
        """GIVEN --install-codegraph flag y codegraph no detectado WHEN run()
        THEN install_codegraph es llamado sin pasar por prompt (CI-safe)."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(True, {"which": "/p"})), \
             patch.object(installer, "detect_codegraph", return_value=(False, {})), \
             patch.object(installer, "prompt_codegraph_yn") as mock_prompt, \
             patch.object(installer, "install_codegraph", return_value=(True, "ok")) as mock_install, \
             patch.object(installer, "register_codegraph_mcp", return_value="created"), \
             patch.object(installer, "install_assets", return_value={
                 "skills_deposited": 6, "shared_deposited": 3,
                 "agents_deposited": 6, "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args(install_codegraph=True))

        assert result == installer.EXIT_OK
        mock_install.assert_called_once()
        mock_prompt.assert_not_called()

    def test_exception_in_codegraph_step_does_not_abort_run(self):
        """GIVEN install_codegraph lanza excepción inesperada WHEN run()
        THEN retorna EXIT_OK (try/except defensa en profundidad R-INST-05)."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(True, {"which": "/p"})), \
             patch.object(installer, "detect_codegraph", return_value=(False, {})), \
             patch.object(installer, "prompt_codegraph_yn", return_value="y"), \
             patch.object(installer, "install_codegraph", side_effect=RuntimeError("boom")), \
             patch.object(installer, "install_assets", return_value={
                 "skills_deposited": 6, "shared_deposited": 3,
                 "agents_deposited": 6, "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args())

        assert result == installer.EXIT_OK

    def test_print_report_includes_codegraph_section(self, capsys):
        """GIVEN report con codegraph info WHEN print_report() THEN el output menciona codegraph."""
        from forge.installer import print_report

        report = {
            "engram": {"which": "/usr/bin/engram"},
            "assets": {
                "skills_deposited": 6,
                "shared_deposited": 3,
                "agents_deposited": 6,
                "warnings": [],
            },
            "codegraph": {"status": "installed", "msg": "codegraph instalado en /home/.codegraph/bin/codegraph"},
        }
        print_report(report)
        captured = capsys.readouterr()
        assert "codegraph" in captured.out.lower()

    def test_print_report_codegraph_already_present(self, capsys):
        """GIVEN codegraph ya instalado (status='already_present') WHEN print_report()
        THEN menciona que ya estaba instalado."""
        from forge.installer import print_report

        report = {
            "engram": {"which": "/usr/bin/engram"},
            "assets": {
                "skills_deposited": 6,
                "shared_deposited": 3,
                "agents_deposited": 6,
                "warnings": [],
            },
            "codegraph": {"status": "already_present", "msg": "/usr/local/bin/codegraph"},
        }
        print_report(report)
        captured = capsys.readouterr()
        assert "codegraph" in captured.out.lower()

    def test_print_report_codegraph_skipped(self, capsys):
        """GIVEN codegraph omitido (status='skipped') WHEN print_report()
        THEN el output menciona que fue omitido."""
        from forge.installer import print_report

        report = {
            "engram": {"which": "/usr/bin/engram"},
            "assets": {
                "skills_deposited": 6,
                "shared_deposited": 3,
                "agents_deposited": 6,
                "warnings": [],
            },
            "codegraph": {"status": "skipped", "msg": "omitido por --skip-codegraph"},
        }
        print_report(report)
        captured = capsys.readouterr()
        assert "codegraph" in captured.out.lower()


# ---------------------------------------------------------------------------
# Context7 MCP — TestRegisterContext7Mcp (TDD RED → GREEN)
# ---------------------------------------------------------------------------


class TestRegisterContext7Mcp:
    """Verifica register_context7_mcp() — merge idempotente en ~/.claude.json. R-CTX-01, R-CTX-03, R-CTX-05."""

    def test_creates_mcp_block_when_file_missing(self, tmp_path, monkeypatch):
        """GIVEN ~/.claude.json no existe WHEN register_context7_mcp()
        THEN crea el archivo con mcpServers.context7 y retorna 'created'."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)

        status = installer.register_context7_mcp()

        assert status == "created"
        assert claude_json.exists()
        data = json.loads(claude_json.read_text(encoding="utf-8"))
        assert "mcpServers" in data
        assert "context7" in data["mcpServers"]
        ctx = data["mcpServers"]["context7"]
        assert ctx["command"] == "npx"
        assert "-y" in ctx["args"]
        assert "@upstash/context7-mcp" in ctx["args"]

    def test_merges_without_overwriting_existing_config(self, tmp_path, monkeypatch):
        """GIVEN ~/.claude.json con config previa (incluye mcpServers.codegraph) WHEN register_context7_mcp()
        THEN preserva las claves existentes y agrega mcpServers.context7."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        existing_config = {
            "theme": "dark",
            "mcpServers": {
                "codegraph": {
                    "type": "stdio",
                    "command": "codegraph",
                    "args": ["serve", "--mcp"],
                }
            },
        }
        claude_json.write_text(
            json.dumps(existing_config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)

        status = installer.register_context7_mcp()

        assert status in ("created", "merged")
        data = json.loads(claude_json.read_text(encoding="utf-8"))
        # Config existente preservada
        assert data.get("theme") == "dark"
        assert "codegraph" in data["mcpServers"], "El bloque codegraph existente debe preservarse"
        # Context7 agregado
        assert "context7" in data["mcpServers"]

    def test_idempotent_second_call_returns_present(self, tmp_path, monkeypatch):
        """GIVEN register_context7_mcp() ya fue llamado WHEN se llama de nuevo
        THEN retorna 'present' y NO modifica el archivo."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)

        installer.register_context7_mcp()
        content_after_first = claude_json.read_text(encoding="utf-8")

        status2 = installer.register_context7_mcp()

        assert status2 == "present"
        content_after_second = claude_json.read_text(encoding="utf-8")
        assert content_after_first == content_after_second

    def test_creates_backup_before_writing(self, tmp_path, monkeypatch):
        """GIVEN ~/.claude.json con config existente WHEN register_context7_mcp()
        THEN crea backup .claude.json.forge-bak con el contenido original."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        original_content = json.dumps({"theme": "light"}, indent=2)
        claude_json.write_text(original_content, encoding="utf-8")
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)

        installer.register_context7_mcp()

        backup = tmp_path / ".claude.json.forge-bak"
        assert backup.exists(), "Debe existir el archivo de backup .claude.json.forge-bak"
        assert backup.read_text(encoding="utf-8") == original_content

    def test_corrupt_json_treated_as_empty(self, tmp_path, monkeypatch):
        """GIVEN ~/.claude.json existe pero contiene JSON inválido WHEN register_context7_mcp()
        THEN trata el archivo como vacío y retorna 'created' o 'merged' sin lanzar excepción."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        claude_json.write_text("{ invalid json {{", encoding="utf-8")
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)

        # No debe lanzar excepción
        status = installer.register_context7_mcp()

        assert status in ("created", "merged")
        # El archivo resultante debe ser JSON válido
        data = json.loads(claude_json.read_text(encoding="utf-8"))
        assert "mcpServers" in data
        assert "context7" in data["mcpServers"]

    def test_injects_api_key_from_env(self, tmp_path, monkeypatch):
        """GIVEN CONTEXT7_API_KEY está seteada WHEN register_context7_mcp()
        THEN el bloque MCP incluye --api-key <valor> en args."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)
        monkeypatch.setenv("CONTEXT7_API_KEY", "test-key-abc123")

        installer.register_context7_mcp()

        data = json.loads(claude_json.read_text(encoding="utf-8"))
        ctx = data["mcpServers"]["context7"]
        assert "--api-key" in ctx["args"]
        key_idx = ctx["args"].index("--api-key")
        assert ctx["args"][key_idx + 1] == "test-key-abc123"

    def test_no_api_key_when_env_absent(self, tmp_path, monkeypatch):
        """GIVEN CONTEXT7_API_KEY no está definida WHEN register_context7_mcp()
        THEN el bloque MCP NO incluye --api-key (usa pool anónimo)."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)
        monkeypatch.delenv("CONTEXT7_API_KEY", raising=False)

        installer.register_context7_mcp()

        data = json.loads(claude_json.read_text(encoding="utf-8"))
        ctx = data["mcpServers"]["context7"]
        assert "--api-key" not in ctx["args"]

    def test_env_key_not_mutating_constant(self, tmp_path, monkeypatch):
        """GIVEN CONTEXT7_API_KEY está seteada WHEN register_context7_mcp()
        THEN _CONTEXT7_MCP_BLOCK constante NO muta (--api-key no aparece en la constante)."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)
        monkeypatch.setenv("CONTEXT7_API_KEY", "mutacion-test-key")

        installer.register_context7_mcp()

        # La constante original no debe contener --api-key
        assert "--api-key" not in installer._CONTEXT7_MCP_BLOCK["args"]

    def test_present_status_skips_backup(self, tmp_path, monkeypatch):
        """GIVEN mcpServers.context7 ya existe WHEN register_context7_mcp() segunda vez
        THEN retorna 'present' y NO sobreescribe el backup."""
        from forge import installer

        claude_json = tmp_path / ".claude.json"
        monkeypatch.setattr(installer, "CODEGRAPH_CLAUDE_JSON", claude_json)

        # Primera llamada: registra y crea backup
        installer.register_context7_mcp()
        backup = tmp_path / ".claude.json.forge-bak"
        backup_content_after_first = backup.read_text(encoding="utf-8") if backup.exists() else None

        # Segunda llamada: debe retornar present
        status2 = installer.register_context7_mcp()

        assert status2 == "present"
        # El backup no debe cambiar entre la primera y la segunda llamada
        if backup.exists() and backup_content_after_first is not None:
            assert backup.read_text(encoding="utf-8") == backup_content_after_first


# ---------------------------------------------------------------------------
# Context7 MCP — TestRunContext7 (TDD RED → GREEN para flags en run())
# ---------------------------------------------------------------------------


class TestRunContext7:
    """Verifica integración de Context7 en run() — flags --skip-context7/--install-context7. R-CTX-01."""

    def _make_args(
        self,
        install_engram=False,
        skip_engram_check=True,
        skip_codegraph=True,
        install_codegraph=False,
        skip_context7=False,
        install_context7=False,
    ):
        import argparse
        return argparse.Namespace(
            install_engram=install_engram,
            skip_engram_check=skip_engram_check,
            skip_codegraph=skip_codegraph,
            install_codegraph=install_codegraph,
            skip_context7=skip_context7,
            install_context7=install_context7,
        )

    def test_skip_context7_omits_registration(self):
        """GIVEN --skip-context7 WHEN run() THEN register_context7_mcp NO es llamado."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(True, {"which": "/p"})), \
             patch.object(installer, "register_context7_mcp") as mock_reg, \
             patch.object(installer, "install_assets", return_value={
                 "skills_deposited": 6, "shared_deposited": 3,
                 "agents_deposited": 6, "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args(skip_context7=True))

        assert result == installer.EXIT_OK
        mock_reg.assert_not_called()

    def test_install_context7_registers_without_prompt(self):
        """GIVEN --install-context7 y context7 no registrado WHEN run()
        THEN register_context7_mcp es llamado sin pasar por prompt (CI-safe)."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(True, {"which": "/p"})), \
             patch.object(installer, "register_context7_mcp", return_value="created") as mock_reg, \
             patch.object(installer, "prompt_context7_yn") as mock_prompt, \
             patch.object(installer, "install_assets", return_value={
                 "skills_deposited": 6, "shared_deposited": 3,
                 "agents_deposited": 6, "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args(install_context7=True))

        assert result == installer.EXIT_OK
        mock_reg.assert_called_once()
        mock_prompt.assert_not_called()

    def test_skip_takes_precedence_over_install(self):
        """GIVEN --skip-context7 y --install-context7 juntos WHEN run()
        THEN skip tiene precedencia, register_context7_mcp NO es llamado."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(True, {"which": "/p"})), \
             patch.object(installer, "register_context7_mcp") as mock_reg, \
             patch.object(installer, "install_assets", return_value={
                 "skills_deposited": 6, "shared_deposited": 3,
                 "agents_deposited": 6, "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args(skip_context7=True, install_context7=True))

        assert result == installer.EXIT_OK
        mock_reg.assert_not_called()

    def test_context7_failure_does_not_change_exit_code(self):
        """GIVEN register_context7_mcp lanza excepción WHEN run()
        THEN retorna EXIT_OK (fallo graceful R-CTX-05)."""
        from forge import installer

        with patch.object(installer, "detect_engram", return_value=(True, {"which": "/p"})), \
             patch.object(installer, "register_context7_mcp", side_effect=RuntimeError("boom")), \
             patch.object(installer, "install_assets", return_value={
                 "skills_deposited": 6, "shared_deposited": 3,
                 "agents_deposited": 6, "warnings": []}), \
             patch.object(installer, "inject_orchestrator_rule", return_value="created"), \
             patch.object(installer, "print_report"):
            result = installer.run(self._make_args())

        assert result == installer.EXIT_OK
