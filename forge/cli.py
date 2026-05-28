"""forge CLI entry point.

Subcomandos disponibles en v0.1.0:
    forge --version          Imprime la versión instalada.
    forge install --global   Deposita skills, agents y commands en ~/.claude/
                             para que Claude Code los descubra.
                             [NO IMPLEMENTADO en v0.1.0 — placeholder]
    forge --help             Muestra ayuda.

La instalación por proyecto se hace desde Claude Code con la skill /fg-setup,
que invoca a forge.bootstrap en el proyecto activo.
"""

import argparse
import sys

from . import __version__


def cmd_install(args: argparse.Namespace) -> int:
    """Depositar skills/agents/commands en ~/.claude/."""
    if not args.global_install:
        sys.stderr.write(
            "forge install: por ahora solo se soporta el modo --global.\n"
            "Uso: forge install --global\n"
        )
        return 2

    sys.stderr.write(
        "forge install --global: NO IMPLEMENTADO en v0.1.0.\n"
        "\n"
        "Este subcomando debe depositar los siguientes archivos en ~/.claude/:\n"
        "  - skills/forge/fg-*.md (6 skills)\n"
        "  - agents/forge-*.md (6 sub-agentes)\n"
        "  - commands/fg-*.md (slash commands)\n"
        "  - skills/forge-shared/*.md (referencias compartidas)\n"
        "\n"
        "Pendiente para próxima iteración. Mientras tanto, las skills se pueden\n"
        "instalar manualmente copiando los archivos del paquete a ~/.claude/.\n"
    )
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forge",
        description="Spec-Driven Development workflow for Claude Code in critical environments.",
    )
    parser.add_argument("--version", action="version", version=f"forge {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=False)

    install_parser = subparsers.add_parser(
        "install",
        help="Instalar el harness de forge globalmente en ~/.claude/.",
    )
    install_parser.add_argument(
        "--global",
        dest="global_install",
        action="store_true",
        help="Depositar skills, agents y commands en ~/.claude/ (modo soportado en v0.1.0).",
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
