"""Entry point del CLI de forge.

Subcomandos:
    forge --version                    Imprime la versión instalada.
    forge install                      Deposita skills, agents y registra el MCP de engram
                                       en ~/.claude/. Implementado en forge/installer.py.
    forge install --install-engram     Instala engram automáticamente, sin prompt.
    forge install --skip-engram-check  Saltea la detección de engram, solo deposita assets.
    forge install --skip-codegraph     Omite por completo la instalación de CodeGraph.
    forge install --install-codegraph  Instala CodeGraph automáticamente sin prompt (CI-safe).
    forge install --skip-context7      Omite por completo el registro de Context7 MCP.
    forge install --install-context7   Registra Context7 MCP sin prompt (CI-safe).
    forge install --skip-pii-hook      Omite el auto-registro del hook PII (UserPromptSubmit).
    forge --help                       Muestra la ayuda.

El setup a nivel proyecto se hace desde Claude Code con la skill /fg-setup,
que invoca forge.bootstrap en el proyecto activo.
"""

import argparse
import sys

from . import __version__


def cmd_install(args: argparse.Namespace) -> int:
    """Dispatch fino a installer.run(args). Devuelve el exit code."""
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
    install_parser.add_argument(
        "--skip-pii-hook",
        dest="skip_pii_hook",
        action="store_true",
        help=(
            "Omitir el auto-registro del hook PII (UserPromptSubmit) en "
            "~/.claude/settings.json. El filtro de redacción no se activará hasta "
            "registrarlo manualmente."
        ),
    )
    install_parser.add_argument(
        "--skip-guard-hook",
        dest="skip_guard_hook",
        action="store_true",
        help=(
            "Omitir el auto-registro del hook de guardrails (PreToolUse) en "
            "~/.claude/settings.json. Las reglas de docs/auditoria/guardrails.yaml "
            "no se evaluarán hasta registrarlo manualmente."
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
