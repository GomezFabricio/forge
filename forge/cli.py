"""forge CLI entry point.

Subcommands:
    forge --version                  Print installed version.
    forge install                    Deposit skills, agents and register engram MCP
                                     in ~/.claude/. Implemented in forge/installer.py.
    forge install --install-engram   Auto-install engram without prompt.
    forge install --skip-engram-check  Skip engram detection, deposit assets only.
    forge --help                     Show help.

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
