#!/usr/bin/env python3
"""Bootstrap de forge en un proyecto.

Invocado por la skill /fg-setup (Markdown). Hace todo el trabajo de instalación
inicial: detectar stack, generar docs/auditoria/config.yaml con defaults, mergear
CLAUDE.md, inicializar CodeGraph, generar skill registry placeholder,
actualizar .gitignore.

Uso:
    python -m forge.bootstrap [--project-root PATH] [--json]

Idempotente: re-ejecutar no rompe nada, solo agrega lo faltante. Si
docs/auditoria/config.yaml ya existe, el bootstrap NO lo sobrescribe — los
cambios manuales del dev se preservan.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

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
        root / "docs" / "auditoria" / "cambios",
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


AUDIT_CONFIG_TEMPLATE = """\
# docs/auditoria/config.yaml
#
# Configuración del workflow forge para este proyecto.
# - context: lo regenera /fg-setup en cada corrida (detección automática del stack).
# - rules: lo edita el equipo a mano para ajustar el comportamiento del workflow.
#
# IMPORTANTE: si reejecutás /fg-setup, este archivo se PRESERVA — los cambios manuales
# no se pierden. Para resetear a defaults, borrá este archivo y volvé a correr /fg-setup.

schema: forge

context:
  stacks:                             # stacks detectados por /fg-setup (python, node, etc.)
{stacks_yaml}
  test_runner:                        # runner detectado al correr /fg-setup
{test_runner_yaml}

rules:
  workflow:
    # cycle_mode: cómo corren las 4 fases del workflow forge (plan → design → implement → review).
    #   "interactive" = pausa entre fases para que el dev revise antes de seguir.
    #   "automatic"   = corre las 4 fases sin parar, muestra solo el resultado final.
    # NOTA: este es el default sugerido; /fg-plan paso 0 lo pregunta una vez por sesión
    # al primer comando del ciclo y cachea la respuesta. "1 sesión = 1 ciclo" es la norma sana.
    cycle_mode: interactive

  pr_size:
    # Cuando /fg-design cierra, calcula un "Review Workload Forecast" estimando
    # las líneas que va a tener el PR. Este bloque controla qué hacer con ese forecast.

    # budget_lines: umbral de líneas a partir del cual el PR se considera "grande".
    # Heurística común: 400 líneas es el techo confortable para una review humana de calidad.
    budget_lines: 400

    # suggest_split: cuando el forecast supera el budget, ¿sugerir partir en chained PRs?
    #   false = no sugerir (default — el dev decide cuándo y cómo partir).
    #   true  = sugerir explícitamente partir en chained PRs.
    # Esto es SUGERENCIA, no acción: forge nunca crea ramas o PRs sin opt-in explícito.
    suggest_split: false

    # enforcement: cuán estricto es el control del budget. Tres modos:
    #   "off"   = nunca menciona el budget. 1 issue = 1 MR (default oficina típica).
    #   "warn"  = avisa en /fg-design y /fg-review cuando se supera, pero NO bloquea.
    #             Útil para devs / freelancers atentos que quieren visibilidad sin fricción.
    #   "block" = exige documentar `size:exception` en el PR body para mergear cuando supera.
    #             Útil para equipos con presión real sobre calidad de review.
    enforcement: "off"

  implement:
    # tdd: opt-in al ciclo Strict TDD de forge (RED → GREEN → TRIANGULATE → REFACTOR).
    #   false = modo estándar (default — /fg-implement avisa que TDD no está activo).
    #   true  = /fg-implement carga _shared/strict-tdd.md y exige el ciclo de 7 pasos.
    # Para activar: editar este archivo y commitear. El cambio queda versionado.
    tdd: false

    # test_command: comando que /fg-implement usa para correr tests entre tareas.
    # Si está vacío, fallback a context.test_runner.command. Si los dos están vacíos, aborta.
    test_command: ""

    # max_tasks_per_batch: cuántas tareas /fg-implement procesa antes de cortar y guardar
    # progreso. Si /fg-design generó más tareas que este límite, /fg-implement corta cuando
    # llega al límite, guarda el progreso en engram (forge/{{cambio}}/implement-progress) y
    # reporta al dev. La próxima invocación retoma desde donde quedó.
    # NOTA: idealmente cada batch corre en una sesión nueva (norma "1 sesión = 1 ciclo").
    max_tasks_per_batch: 20

  review:
    # test_command: comando que /fg-review usa para correr la suite completa al validar.
    # Fallback chain: rules.review.test_command → rules.implement.test_command → context.test_runner.command.
    test_command: ""

    # coverage_threshold: cobertura mínima requerida sobre archivos modificados.
    #   0 = sin enforcement (default — sólo reporta coverage, no bloquea).
    #   N>0 = bloquea cierre del ciclo si algún archivo cambiado queda por debajo.
    coverage_threshold: 0
"""


def _build_stacks_yaml(stacks: list) -> str:
    """Render the stacks list as yaml lines with 4-space indent."""
    if not stacks:
        return "    []"
    return "\n".join(f"    - {s}" for s in stacks)


def _build_test_runner_yaml(runner: str, runner_command: str, detected_from: str) -> str:
    """Render the test_runner block as yaml lines with 4-space indent."""
    if not runner:
        return "    null"
    lines = [
        f"    name: {runner}",
        f"    command: {runner_command}",
        f"    detected_from: {detected_from}",
    ]
    return "\n".join(lines)


def create_audit_config(root: Path, stacks: list, runner: str, runner_command: str, detected_from: str) -> str:
    path = root / "docs" / "auditoria" / "config.yaml"
    if path.exists():
        return "preserved"

    content = AUDIT_CONFIG_TEMPLATE.format(
        stacks_yaml=_build_stacks_yaml(stacks),
        test_runner_yaml=_build_test_runner_yaml(runner, runner_command, detected_from),
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
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
            "No se detectó test runner. docs/auditoria/config.yaml queda con test_runner: null. "
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
    print(f"  docs/auditoria/config.yaml: {report['audit_config']}")
    for name, status in report["config_templates"].items():
        print(f"  config/{name}: {status}")
    print(f"  .atl/skill-registry.md: {report['skill_registry']}")
    print(f"  .gitignore: {report['gitignore']}")
    print()
    if report["audit_config"] == "created":
        print("Nota: TDD está OFF por default. Para activarlo, editá docs/auditoria/config.yaml")
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
