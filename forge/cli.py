"""forge CLI entry point.

Subcommands:
    forge --version                    Print installed version.
    forge install                      Deposit skills, agents and register engram MCP
                                       in ~/.claude/. Implemented in forge/installer.py.
    forge install --install-engram     Auto-install engram without prompt.
    forge install --skip-engram-check  Skip engram detection, deposit assets only.
    forge install --skip-codegraph     Skip CodeGraph installation entirely.
    forge install --install-codegraph  Auto-install CodeGraph without prompt (CI-safe).
    forge install --skip-context7      Skip Context7 MCP registration entirely.
    forge install --install-context7   Register Context7 MCP without prompt (CI-safe).
    forge --help                       Show help.

Project-level setup is done from Claude Code with the /fg-setup skill,
which invokes forge.bootstrap in the active project.
"""

import argparse
import sys

from . import __version__


def cmd_install(args: argparse.Namespace) -> int:
    """Thin dispatch to installer.run(args). Returns exit code."""
    from forge.installer import run as installer_run
    return installer_run(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forge",
        description="Spec-Driven Development workflow for Claude Code in critical environments.",
    )
    parser.add_argument("--version", action="version", version=f"forge {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=False)

    install_parser = subparsers.add_parser(
        "install",
        help="Instalar forge en ~/.claude/ (skills, agents, MCP de engram).",
    )
    install_parser.add_argument(
        "--install-engram",
        dest="install_engram",
        action="store_true",
        help=(
            "Instalar engram automáticamente si falta, sin prompt (non-interactive). "
            "Si engram ya está detectado, es no-op. "
            "Tiene precedencia sobre --skip-engram-check."
        ),
    )
    install_parser.add_argument(
        "--skip-engram-check",
        dest="skip_engram_check",
        action="store_true",
        help=(
            "Saltar la detección de engram y depositar solo skills/agents. "
            "--install-engram tiene precedencia si ambos se pasan."
        ),
    )
    install_parser.add_argument(
        "--skip-codegraph",
        dest="skip_codegraph",
        action="store_true",
        help=(
            "Omitir completamente la instalación y registro de CodeGraph. "
            "Equivalente a responder N al prompt de CodeGraph."
        ),
    )
    install_parser.add_argument(
        "--install-codegraph",
        dest="install_codegraph",
        action="store_true",
        help=(
            "Instalar CodeGraph automáticamente si falta, sin prompt (non-interactive / CI). "
            "Si CodeGraph ya está detectado, registra el MCP sin reinstalar. "
            "--skip-codegraph tiene precedencia si ambos se pasan."
        ),
    )
    install_parser.add_argument(
        "--skip-context7",
        dest="skip_context7",
        action="store_true",
        help=(
            "Omitir completamente el registro de Context7 MCP. "
            "Equivalente a responder N al prompt de Context7."
        ),
    )
    install_parser.add_argument(
        "--install-context7",
        dest="install_context7",
        action="store_true",
        help=(
            "Registrar Context7 MCP automáticamente sin prompt (non-interactive / CI). "
            "--skip-context7 tiene precedencia si ambos se pasan."
        ),
    )
    install_parser.set_defaults(func=cmd_install)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
