"""Tests de forge.cli — parser y dispatch de install. T02, T13.

Cubre:
- TestBuildParser    — --global ausente; --install-engram; --skip-engram-check
- TestCmdInstall     — thin dispatch a installer.run; flags individualmente y combinados

Constraints (CC-*):
- CC-TMP-PATH: no filesystem I/O directo en estos tests.
- CC-NO-REAL-PROC: installer.run siempre mockeado.
"""

import argparse
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# TestBuildParser — T02 + T13
# ---------------------------------------------------------------------------


class TestBuildParser:
    """Verifica build_parser() — flags del subcomando install. T02, T13."""

    def test_global_flag_removed(self):
        """GIVEN el parser construido WHEN se parsea 'install --global'
        THEN lanza SystemExit (flag desconocido)."""
        from forge.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["install", "--global"])

    def test_install_engram_flag_present(self):
        """GIVEN el parser construido WHEN se parsea 'install --install-engram'
        THEN args.install_engram es True."""
        from forge.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["install", "--install-engram"])
        assert args.install_engram is True

    def test_skip_engram_check_flag_present(self):
        """GIVEN el parser construido WHEN se parsea 'install --skip-engram-check'
        THEN args.skip_engram_check es True."""
        from forge.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["install", "--skip-engram-check"])
        assert args.skip_engram_check is True

    def test_install_engram_default_false(self):
        """GIVEN el parser WHEN 'install' sin flags THEN install_engram es False."""
        from forge.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["install"])
        assert args.install_engram is False

    def test_skip_engram_check_default_false(self):
        """GIVEN el parser WHEN 'install' sin flags THEN skip_engram_check es False."""
        from forge.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["install"])
        assert args.skip_engram_check is False

    def test_skip_pii_hook_flag_present(self):
        """GIVEN el parser WHEN se parsea 'install --skip-pii-hook'
        THEN args.skip_pii_hook es True."""
        from forge.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["install", "--skip-pii-hook"])
        assert args.skip_pii_hook is True

    def test_skip_pii_hook_default_false(self):
        """GIVEN el parser WHEN 'install' sin flags THEN skip_pii_hook es False."""
        from forge.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["install"])
        assert args.skip_pii_hook is False

    def test_both_flags_parseable(self):
        """GIVEN el parser WHEN 'install --install-engram --skip-engram-check'
        THEN ambos flags son True (el dispatch decide la precedencia)."""
        from forge.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["install", "--install-engram", "--skip-engram-check"])
        assert args.install_engram is True
        assert args.skip_engram_check is True

    def test_install_subcommand_func_is_cmd_install(self):
        """GIVEN el parser WHEN 'install' THEN args.func apunta a cmd_install."""
        from forge.cli import build_parser, cmd_install
        parser = build_parser()
        args = parser.parse_args(["install"])
        assert args.func is cmd_install


# ---------------------------------------------------------------------------
# TestCmdInstall — thin dispatch. T02, T13
# ---------------------------------------------------------------------------


class TestCmdInstall:
    """Verifica cmd_install() — thin dispatch a installer.run. T02, T13."""

    def test_dispatches_to_installer_run(self):
        """GIVEN cmd_install(args) WHEN llamado THEN delega a installer.run(args)."""
        from forge.cli import cmd_install
        args = argparse.Namespace(install_engram=False, skip_engram_check=False)

        with patch("forge.installer.run", return_value=0) as mock_run:
            result = cmd_install(args)

        mock_run.assert_called_once_with(args)
        assert result == 0

    def test_returns_exit_code_from_installer(self):
        """GIVEN installer.run retorna 10 WHEN cmd_install THEN retorna 10."""
        from forge.cli import cmd_install
        args = argparse.Namespace(install_engram=False, skip_engram_check=False)

        with patch("forge.installer.run", return_value=10):
            result = cmd_install(args)

        assert result == 10

    def test_install_engram_flag_forwarded(self):
        """GIVEN args con install_engram=True WHEN cmd_install THEN installer.run recibe el args completo."""
        from forge.cli import cmd_install
        args = argparse.Namespace(install_engram=True, skip_engram_check=False)

        with patch("forge.installer.run", return_value=0) as mock_run:
            cmd_install(args)

        call_args = mock_run.call_args[0][0]
        assert call_args.install_engram is True

    def test_skip_engram_check_flag_forwarded(self):
        """GIVEN args con skip_engram_check=True WHEN cmd_install THEN installer.run recibe el args."""
        from forge.cli import cmd_install
        args = argparse.Namespace(install_engram=False, skip_engram_check=True)

        with patch("forge.installer.run", return_value=0) as mock_run:
            cmd_install(args)

        call_args = mock_run.call_args[0][0]
        assert call_args.skip_engram_check is True


class TestPromptUserYnCli:
    """Verifica prompt_user_yn() — casos de input. T13 (complementa TestPromptUserYn en test_installer)."""

    def test_Y_uppercase_returns_y(self):
        """GIVEN input 'Y' WHEN prompt_user_yn() THEN retorna 'y'."""
        from forge.installer import prompt_user_yn
        with patch("builtins.input", return_value="Y"):
            assert prompt_user_yn() == "y"

    def test_yes_mixed_case_returns_y(self):
        """GIVEN input 'Yes' WHEN prompt_user_yn() THEN retorna 'y'."""
        from forge.installer import prompt_user_yn
        with patch("builtins.input", return_value="Yes"):
            assert prompt_user_yn() == "y"
