#!/usr/bin/env python3
"""Bootstrap de forge en un proyecto.

Invocado por la skill /fg-setup (Markdown). Hace todo el trabajo de instalación
inicial: detectar stack, generar docs/audit/config.yaml con defaults, mergear
CLAUDE.md, inicializar CodeGraph, generar skill registry placeholder,
actualizar .gitignore.

Uso:
    python -m forge.bootstrap [--project-root PATH] [--json]

Idempotente: re-ejecutar no rompe nada, solo agrega lo faltante. Si
docs/audit/config.yaml ya existe, el bootstrap NO lo sobrescribe — los
cambios manuales del dev se preservan.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("bootstrap: pyyaml no instalado. Instalá con `pip install pyyaml`.\n")
    sys.exit(1)


PACKAGE_ROOT = Path(__file__).resolve().parent.parent

STACK_MANIFESTS = {
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "setup.py": "Python",
    "package.json": "Node",
    "go.mod": "Go",
    "pom.xml": "Java",
    "build.gradle": "Java",
    "Cargo.toml": "Rust",
    "composer.json": "PHP",
    "Gemfile": "Ruby",
}

TEST_RUNNERS = {
    "Python": [
        ("pytest", ["pytest.ini", "pyproject.toml", "setup.cfg"], "pytest"),
        ("unittest", [], "python -m unittest"),
    ],
    "Node": [
        ("vitest", ["vitest.config.js", "vitest.config.ts", "vite.config.js", "vite.config.ts"], "npx vitest run"),
        ("jest", ["jest.config.js", "jest.config.ts"], "npx jest"),
    ],
    "Go": [
        ("go test", ["go.mod"], "go test ./..."),
    ],
    "Java": [
        ("maven", ["pom.xml"], "mvn test"),
        ("gradle", ["build.gradle"], "./gradlew test"),
    ],
    "Rust": [
        ("cargo test", ["Cargo.toml"], "cargo test"),
    ],
}


def detect_stack(root: Path) -> list:
    detected = []
    for manifest, lang in STACK_MANIFESTS.items():
        if (root / manifest).exists() and lang not in detected:
            detected.append(lang)
    return detected


def detect_test_runner(root: Path, stacks: list) -> tuple:
    for stack in stacks:
        for runner_name, indicators, command in TEST_RUNNERS.get(stack, []):
            matching = [ind for ind in indicators if (root / ind).exists()]
            if not indicators or matching:
                detected_from = matching[0] if matching else ""
                return runner_name, command, detected_from
    return None, None, ""


def ensure_dirs(root: Path) -> list:
    paths = [
        root / "docs" / "audit" / "changes",
        root / ".atl",
        root / "config",
    ]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    return [str(p.relative_to(root)) for p in paths]


def copy_if_missing(src: Path, dst: Path) -> bool:
    if dst.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def extract_section(content: str, marker: str) -> str:
    """Extrae la sección que comienza en `marker` hasta el próximo heading nivel 2."""
    start = content.find(marker)
    if start == -1:
        return ""
    lines = content[start:].split("\n")
    section_lines = [lines[0]]
    for line in lines[1:]:
        if line.startswith("## "):
            break
        section_lines.append(line)
    return "\n".join(section_lines)


def merge_or_create_claude_md(root: Path) -> str:
    template_src = PACKAGE_ROOT / "templates" / "CLAUDE-md-institucional.md"
    claude_md = root / "CLAUDE.md"
    if not claude_md.exists():
        shutil.copy2(template_src, claude_md)
        return "created"
    existing = claude_md.read_text(encoding="utf-8")
    template_content = template_src.read_text(encoding="utf-8")
    sdd_markers = [
        "## Persona del orquestador",
        "## Engram",
        "## Strict TDD Mode",
        "## Workflow de las skills",
        "## Idioma",
    ]
    appended = []
    for marker in sdd_markers:
        if marker not in existing:
            section = extract_section(template_content, marker)
            if section:
                if not existing.endswith("\n"):
                    existing += "\n"
                existing += "\n" + section.rstrip() + "\n"
                appended.append(marker)
    if appended:
        claude_md.write_text(existing, encoding="utf-8")
        return f"merged ({len(appended)} sections appended)"
    return "preserved"


def copy_config_templates(root: Path) -> dict:
    results = {}
    for filename in ["modulos-transversales.yaml"]:
        src = PACKAGE_ROOT / "config" / filename
        dst = root / "config" / filename
        results[filename] = "created" if copy_if_missing(src, dst) else "preserved"
    return results


def init_codegraph(root: Path) -> tuple:
    if not shutil.which("codegraph"):
        return None, "codegraph binario no encontrado en PATH"
    db_path = root / ".codegraph" / "codegraph.db"
    if db_path.exists():
        return "preserved", None
    try:
        subprocess.run(
            ["codegraph", "init", "."],
            cwd=str(root),
            check=True,
            capture_output=True,
            timeout=120,
        )
        return "indexed", None
    except subprocess.SubprocessError as e:
        return None, f"codegraph init falló: {e}"


AUDIT_CONFIG_HEADER = """# docs/audit/config.yaml
#
# Configuración del workflow forge para este proyecto.
# El bloque `context` lo regenera /fg-setup en cada corrida (detección automática).
# El bloque `rules` lo edita el equipo a mano: cambiar `implement.tdd` a `true`
# activa Strict TDD para los ciclos del workflow.
"""


def create_audit_config(root: Path, stacks: list, runner: str, runner_command: str, detected_from: str) -> str:
    path = root / "docs" / "audit" / "config.yaml"
    if path.exists():
        return "preserved"

    config = {
        "schema": "forge",
        "context": {
            "stacks": stacks,
            "test_runner": (
                {
                    "name": runner,
                    "command": runner_command,
                    "detected_from": detected_from,
                }
                if runner else None
            ),
        },
        "rules": {
            "implement": {
                "tdd": False,
                "test_command": "",
            },
            "review": {
                "test_command": "",
                "coverage_threshold": 0,
            },
        },
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        AUDIT_CONFIG_HEADER + "\n" + yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return "created"


def update_gitignore(root: Path) -> str:
    gitignore = root / ".gitignore"
    required = [
        "# forge",
        ".codegraph/",
        ".engram/",
        "!.engram/chunks/",
    ]
    if not gitignore.exists():
        gitignore.write_text("\n".join(required) + "\n", encoding="utf-8")
        return "created"
    existing = gitignore.read_text(encoding="utf-8")
    added = [line for line in required if line not in existing]
    if not added:
        return "preserved"
    if not existing.endswith("\n"):
        existing += "\n"
    existing += "\n" + "\n".join(added) + "\n"
    gitignore.write_text(existing, encoding="utf-8")
    return f"updated ({len(added)} lines added)"


def generate_skill_registry_placeholder(root: Path) -> str:
    registry_path = root / ".atl" / "skill-registry.md"
    if registry_path.exists():
        return "preserved"
    registry_path.write_text(
        "# Skill Registry\n\n"
        "Placeholder generado por /fg-setup. La generación real del registry con compact rules\n"
        "es trabajo del skill registry generator (ver _shared/skill-resolver.md). Cuando esté\n"
        "integrado, este archivo se regenera automáticamente con las skills disponibles.\n",
        encoding="utf-8",
    )
    return "placeholder_created"


def run(root: Path) -> dict:
    report = {
        "project_root": str(root),
        "stacks": [],
        "test_runner": None,
        "dirs_ensured": [],
        "claude_md": None,
        "audit_config": None,
        "config_templates": {},
        "codegraph": {"status": None, "warning": None},
        "skill_registry": None,
        "gitignore": None,
        "warnings": [],
    }

    stacks = detect_stack(root)
    report["stacks"] = stacks
    if not stacks:
        report["warnings"].append("No se detectó un stack reconocido (no hay manifiestos típicos).")

    runner, runner_command, detected_from = detect_test_runner(root, stacks)
    report["test_runner"] = (
        {"name": runner, "command": runner_command, "detected_from": detected_from}
        if runner else None
    )
    if not runner:
        report["warnings"].append(
            "No se detectó test runner. docs/audit/config.yaml queda con test_runner: null. "
            "Si después instalás uno, podés re-correr /fg-setup o editar el config a mano."
        )

    report["dirs_ensured"] = ensure_dirs(root)
    report["claude_md"] = merge_or_create_claude_md(root)
    report["audit_config"] = create_audit_config(root, stacks, runner, runner_command, detected_from)

    report["config_templates"] = copy_config_templates(root)

    cg_status, cg_warning = init_codegraph(root)
    report["codegraph"] = {"status": cg_status, "warning": cg_warning}
    if cg_warning:
        report["warnings"].append(cg_warning)

    report["skill_registry"] = generate_skill_registry_placeholder(root)
    report["gitignore"] = update_gitignore(root)

    return report


def print_report(report: dict) -> None:
    print(f"forge instalado en {report['project_root']}\n")
    stacks = report["stacks"]
    print(f"Stack detectado: {', '.join(stacks) if stacks else 'ninguno'}")
    if report["test_runner"]:
        tr = report["test_runner"]
        print(f"Test runner: {tr['command']} ({tr['name']}, detectado de {tr['detected_from']})")
    else:
        print("Test runner: no detectado")
    cg = report["codegraph"]
    if cg["status"] == "indexed":
        print("CodeGraph: índice creado")
    elif cg["status"] == "preserved":
        print("CodeGraph: índice ya existente, preservado")
    else:
        print(f"CodeGraph: no inicializado ({cg.get('warning') or 'sin razón'})")
    print()
    print("Archivos:")
    print(f"  CLAUDE.md: {report['claude_md']}")
    print(f"  docs/audit/config.yaml: {report['audit_config']}")
    for name, status in report["config_templates"].items():
        print(f"  config/{name}: {status}")
    print(f"  .atl/skill-registry.md: {report['skill_registry']}")
    print(f"  .gitignore: {report['gitignore']}")
    print()
    if report["audit_config"] == "created":
        print("Nota: TDD está OFF por default. Para activarlo, editá docs/audit/config.yaml")
        print("      y cambiá rules.implement.tdd a true.")
        print()
    if report["warnings"]:
        print("Advertencias:")
        for w in report["warnings"]:
            print(f"  - {w}")
        print()
    print("Próximo paso: /fg-plan <descripción del cambio que querés hacer>")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap de forge en un proyecto.")
    parser.add_argument("--project-root", default=".", help="Raíz del proyecto donde instalar.")
    parser.add_argument("--json", action="store_true", help="Salida en JSON en vez de texto legible.")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    report = run(root)
    if args.json:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print_report(report)


if __name__ == "__main__":
    main()
