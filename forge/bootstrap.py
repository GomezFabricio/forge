#!/usr/bin/env python3
"""Bootstrap de forge en un proyecto.

Invocado por la skill /fg-setup (Markdown). Hace todo el trabajo de instalación
inicial: detectar stack, generar docs/auditoria/config.yaml con defaults,
inicializar CodeGraph, generar skill registry placeholder, actualizar .gitignore.
NO genera CLAUDE.md (la doctrina del orquestador es global, vía forge install).

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
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

# TODO(forge-bootstrap-package-root): PACKAGE_ROOT broken in non-editable wheel installs
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


def detect_mode(root: Path) -> str:
    """Return 'upgrade' | 'adopt' | 'bootstrap' based on filesystem state.

    upgrade   : (root / '.forge') exists as a directory
    adopt     : (root / '.git') exists OR any known stack manifest is present
    bootstrap : otherwise (empty or unknown project dir)

    Pure filesystem read — no side effects, no mutations (NFR-04).
    """
    if (root / ".forge").exists():
        return "upgrade"
    if (root / ".git").exists():
        return "adopt"
    for manifest in STACK_MANIFESTS:
        if (root / manifest).exists():
            return "adopt"
    return "bootstrap"


def _load_ruamel():
    """Import ruamel.yaml, raising RuntimeError with install instructions if missing."""
    try:
        from ruamel.yaml import YAML  # noqa: PLC0415
        return YAML
    except ImportError as exc:
        raise RuntimeError(
            "ruamel.yaml is required for comment-preserving config updates. "
            "Install it with: pip install ruamel.yaml"
        ) from exc


def needs_detection(root: Path) -> bool:
    """Determine if stack/test_runner detection should re-run.

    Returns True iff:
      - config.yaml does not exist (no detection has been done), OR
      - context.pending_detection is True, OR
      - context.last_detection is null/missing, OR
      - Any project manifest (pyproject.toml, package.json, go.mod, etc.)
        has mtime > last_detection.

    This is the Python helper that backs the Section A.2 lazy detection GATE
    in _shared/fg-phase-common.md. Skills call this; if True, they call
    update_detection_fields() before proceeding.

    Pure filesystem read — no side effects (NFR-04).
    """
    import yaml as _yaml  # noqa: PLC0415

    config_path = root / "docs" / "auditoria" / "config.yaml"
    if not config_path.exists():
        return True

    try:
        config = _yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return True

    context = config.get("context", {}) or {}

    # pending_detection: missing → treat as True (EC-05 graceful migration)
    if context.get("pending_detection", True):
        return True

    # last_detection: null or missing → mtime check always triggers
    last_detection_raw = context.get("last_detection")
    if last_detection_raw is None:
        return True

    try:
        last_detection = datetime.fromisoformat(str(last_detection_raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return True

    # Check if any known manifest has mtime newer than last_detection
    for manifest in STACK_MANIFESTS:
        manifest_path = root / manifest
        if manifest_path.exists():
            mtime = datetime.fromtimestamp(manifest_path.stat().st_mtime, tz=timezone.utc)
            if mtime > last_detection:
                return True

    return False


def update_detection_fields(root: Path, *, mode: str | None = None) -> dict:
    """Re-detect stack/test_runner and update context.* in docs/auditoria/config.yaml.

    Uses ruamel.yaml round-trip to preserve comments and key order in rules.*.
    Mutates ONLY:
      - context.stacks
      - context.test_runner
      - context.last_detection  (datetime.now(timezone.utc).isoformat())
      - context.pending_detection → False
    NEVER mutates rules.*.

    Returns: {"stacks": [...], "test_runner": {...}, "changed": bool}

    EC-03: if config.yaml is missing AND mode == "upgrade", re-creates the file
    using AUDIT_CONFIG_TEMPLATE before proceeding with detection.
    Otherwise (no mode specified), returns {} if config is missing (no-op).
    Idempotent: safe to call repeatedly (NFR-01).
    """
    YAML = _load_ruamel()

    config_path = root / "docs" / "auditoria" / "config.yaml"
    if not config_path.exists():
        if mode == "upgrade":
            # EC-03: corrupted state — recreate config, then proceed
            stacks = detect_stack(root)
            runner, runner_command, detected_from = detect_test_runner(root, stacks)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            last_detection_str = datetime.now(timezone.utc).isoformat()
            content = AUDIT_CONFIG_TEMPLATE.format(
                stacks_yaml=_build_stacks_yaml(stacks),
                test_runner_yaml=_build_test_runner_yaml(runner, runner_command, detected_from),
                last_detection=last_detection_str,
                pending_detection="false",
                vision_skipped="false",
            )
            config_path.write_text(content, encoding="utf-8")
            new_runner = (
                {"name": runner, "command": runner_command, "detected_from": detected_from}
                if runner else None
            )
            return {"stacks": stacks, "test_runner": new_runner, "changed": True}
        return {}

    yaml = YAML()
    yaml.preserve_quotes = True

    with config_path.open(encoding="utf-8") as fh:
        data = yaml.load(fh)

    # Re-run detection
    stacks = detect_stack(root)
    runner, runner_command, detected_from = detect_test_runner(root, stacks)

    # Build new test_runner value
    if runner:
        new_runner = {"name": runner, "command": runner_command, "detected_from": detected_from}
    else:
        new_runner = None

    # Determine changed flag
    old_stacks = list(data.get("context", {}).get("stacks") or [])
    old_runner = data.get("context", {}).get("test_runner")
    if old_runner and isinstance(old_runner, dict):
        old_runner_simple = {"name": old_runner.get("name"), "command": old_runner.get("command"), "detected_from": old_runner.get("detected_from")}
    else:
        old_runner_simple = old_runner

    changed = (sorted(old_stacks) != sorted(stacks)) or (old_runner_simple != new_runner)

    # Mutate ONLY context.* keys
    if "context" not in data:
        from ruamel.yaml.comments import CommentedMap  # noqa: PLC0415
        data["context"] = CommentedMap()

    data["context"]["stacks"] = stacks
    data["context"]["test_runner"] = new_runner
    data["context"]["last_detection"] = datetime.now(timezone.utc).isoformat()
    data["context"]["pending_detection"] = False

    # Write back preserving comments
    buf = StringIO()
    yaml.dump(data, buf)
    config_path.write_text(buf.getvalue(), encoding="utf-8")

    return {"stacks": stacks, "test_runner": new_runner, "changed": changed}


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
  last_detection: {last_detection}    # ISO 8601 UTC timestamp of last detection run (null = never run)
  pending_detection: {pending_detection}  # true = no manifests detected yet; re-run on next skill load
  vision_skipped: {vision_skipped}     # true = dev declinó conversación de visión en bootstrap; false = no aplica o se completó
  is_legacy: false                    # legacy project marker (set to true to activate legacy-impact-analyzer)

rules:
  workflow:
    # cycle_mode: cómo corren las 4 fases del workflow forge (plan → design → implement → review).
    #   "interactive" = pausa entre fases para que el dev revise antes de seguir.
    #   "automatic"   = corre las 4 fases sin parar, muestra solo el resultado final.
    # NOTA: este es el default sugerido; el orquestador lo pregunta una vez por sesión,
    # post-explore, y cachea la respuesta. "1 sesión = 1 ciclo" es la norma sana.
    cycle_mode: interactive

    # ceremonial_threshold: cuánta ceremonia aplica el orquestador en su juicio.
    #   "auto" = el orquestador propone el nivel (Libre/Rápido/Completo) y el dev confirma (default).
    #   "lite" = sesga a Rápido siempre que se pueda; nunca fuerza Completo salvo arquitectura desactualizada.
    #   "full" = fuerza Completo SIEMPRE, sin preguntar (entornos críticos / auditoría estricta).
    ceremonial_threshold: auto

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


GUARDRAILS_TEMPLATE = """\
# templates/guardrails.yaml
#
# Plantilla de guardrails para el hook PreToolUse de forge.
# Copiá este archivo a docs/auditoria/guardrails.yaml en tu proyecto.
#
# El hook evalúa las reglas en orden: la PRIMERA que hace match gana.
# Por eso, las reglas más específicas deben ir antes de las generales.
#
# Acciones disponibles:
#   block   -> el comando NO se ejecuta (permissionDecision: deny).
#             Usá para operaciones verdaderamente irrecuperables.
#   confirm -> Claude Code le pide confirmación al usuario antes de ejecutar.
#             Usá para operaciones peligrosas pero ocasionalmente necesarias.
#
# Kill-switch: si necesitás desactivar todos los guardrails temporalmente,
# seteá la variable de entorno FORGE_GUARD_DISABLE=1.
#
# Importante: la alternativa de cada regla NO debe ser un comando que active
# la misma regla. Si el ejemplo que sugerís también matchea el patrón,
# el guardrail bloquearía su propio remedio.

version: 1

rules:
  # ---------------------------------------------------------------------------
  # Git — operaciones que destruyen historia o descartan trabajo local
  # ---------------------------------------------------------------------------

  # git push --force / git push -f
  # Reescribe historia pública. Alternativa: --force-with-lease verifica que no
  # haya commits de otros que no viste aún.
  - pattern: 'git\\s+push\\s+(--force|-f)(\\s|$)'
    action: confirm
    reason: "git push --force reescribe historia remota y puede descartar commits de otros"
    alternative: "git push --force-with-lease (verifica que no haya commits remotos nuevos antes de forzar)"

  # git reset --hard
  # Descarta commits Y cambios del working tree sin posibilidad de recuperación directa.
  - pattern: 'git\\s+reset\\s+--hard'
    action: confirm
    reason: "git reset --hard descarta commits locales y cambios del working tree de forma irrecuperable"
    alternative: "git stash antes de resetear, o git reset --soft para preservar los cambios en staging"

  # git clean -f / git clean -fd / git clean -fdx
  # Borra archivos untracked. A diferencia de reset, estos archivos no están en git y no se pueden recuperar.
  - pattern: 'git\\s+clean\\s+.*-[a-zA-Z]*f'
    action: confirm
    reason: "git clean -f borra archivos untracked de forma irrecuperable (no están en git)"
    alternative: "git clean -n primero para ver qué se borraría, luego decidir archivo por archivo"

  # git checkout -- . / git restore .
  # Descarta todos los cambios locales del working tree.
  - pattern: 'git\\s+(checkout\\s+--\\s+\\.|restore\\s+\\.)'
    action: confirm
    reason: "descarta todos los cambios locales del working tree de forma irrecuperable"
    alternative: "git stash para guardar los cambios temporalmente antes de descartarlos"

  # ---------------------------------------------------------------------------
  # Filesystem — borrado irrecuperable
  # ---------------------------------------------------------------------------

  # rm -rf
  # Borrado recursivo sin papelera. Irrecuperable.
  # El ancla (?:^|[;&|]\\s*) exige que rm esté en posición de comando: NO matchea
  # `git rm -rf --cached` (operación inofensiva sobre el índice de git).
  - pattern: '(?:^|[;&|]\\s*)(?:sudo\\s+)?rm\\s+.*-[a-zA-Z]*(?:r[a-zA-Z]*f|f[a-zA-Z]*r)'
    action: block
    reason: "rm -rf es irrecuperable — no hay papelera ni undo"
    alternative: "revisá la lista de archivos primero con ls o find, luego borrá los específicos, o mové el directorio a /tmp"

  # ---------------------------------------------------------------------------
  # Docker — destrucción de volúmenes de datos
  # ---------------------------------------------------------------------------

  # docker compose down -v / docker-compose down -v
  # El flag -v borra los volúmenes nombrados — destruye datos persistentes del contenedor.
  - pattern: 'docker[\\s-]compose\\s+down\\s+.*-[a-zA-Z]*v'
    action: block
    reason: "docker compose down -v borra los volúmenes de datos del contenedor (bases de datos, uploads, etc.)"
    alternative: "omitir el flag -v al detener el stack; revisá los volúmenes con docker volume ls antes de borrarlos"

  # ---------------------------------------------------------------------------
  # SQL — destrucción de esquemas y bases de datos
  # ---------------------------------------------------------------------------

  # DROP TABLE / DROP DATABASE (case-insensitive)
  - pattern: 'DROP\\s+(TABLE|DATABASE)'
    action: block
    reason: "DROP TABLE/DATABASE destruye datos de producción de forma irrecuperable"
    alternative: "hacer un backup primero; en desarrollo, usar un nombre de base de datos separado para pruebas"
    ignorecase: true
"""


def create_guardrails_template(root: Path) -> str:
    """Deposit the guardrails template at docs/auditoria/guardrails.yaml.

    Idempotent: does not overwrite an existing file.

    Returns:
        'created'   — the file was created from the template
        'preserved' — the file already existed; no changes made
    """
    dest = root / "docs" / "auditoria" / "guardrails.yaml"
    if dest.exists():
        return "preserved"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(GUARDRAILS_TEMPLATE, encoding="utf-8")
    return "created"


def create_audit_config(
    root: Path,
    stacks: list,
    runner: str,
    runner_command: str,
    detected_from: str,
    *,
    pending_detection: bool = False,
    last_detection: str | None = None,
    vision_skipped: bool = False,
) -> str:
    path = root / "docs" / "auditoria" / "config.yaml"
    if path.exists():
        return "preserved"

    last_detection_str = "null" if last_detection is None else last_detection
    content = AUDIT_CONFIG_TEMPLATE.format(
        stacks_yaml=_build_stacks_yaml(stacks),
        test_runner_yaml=_build_test_runner_yaml(runner, runner_command, detected_from),
        last_detection=last_detection_str,
        pending_detection=str(pending_detection).lower(),
        vision_skipped=str(vision_skipped).lower(),
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "created"


def create_arquitectura_docs(
    root: Path,
    overview_content: str,
    stack_content: str,
) -> dict:
    """Crea docs/arquitectura/{overview,stack}.md. UTF-8. NO overwrite si existen.

    Returns: {"overview": Path, "stack": Path, "created": list[str]}
        created ∈ ([], ["overview"], ["stack"], ["overview", "stack"])
    """
    arch_dir = root / "docs" / "arquitectura"
    arch_dir.mkdir(parents=True, exist_ok=True)

    overview_path = arch_dir / "overview.md"
    stack_path = arch_dir / "stack.md"
    created = []

    if not overview_path.exists():
        overview_path.write_text(overview_content, encoding="utf-8")
        created.append("overview")

    if not stack_path.exists():
        stack_path.write_text(stack_content, encoding="utf-8")
        created.append("stack")

    return {
        "overview": overview_path,
        "stack": stack_path,
        "created": created,
    }


def _load_config_for_round_trip(root: Path):
    """Load docs/auditoria/config.yaml using ruamel round-trip mode.

    Returns (yaml_instance, data, config_path) if config exists, else None.
    Ensures context block exists as CommentedMap.
    """
    config_path = root / "docs" / "auditoria" / "config.yaml"
    if not config_path.exists():
        return None

    YAML = _load_ruamel()
    yaml = YAML()
    yaml.preserve_quotes = True

    with config_path.open(encoding="utf-8") as fh:
        data = yaml.load(fh)

    if "context" not in data:
        from ruamel.yaml.comments import CommentedMap  # noqa: PLC0415
        data["context"] = CommentedMap()

    return yaml, data, config_path


def _write_config_round_trip(yaml, data, config_path: Path) -> None:
    """Write data back to config_path using ruamel dump."""
    buf = StringIO()
    yaml.dump(data, buf)
    config_path.write_text(buf.getvalue(), encoding="utf-8")


def patch_config_stacks(root: Path, stacks: list) -> bool:
    """Round-trip ruamel.yaml. Mutates ONLY context.stacks. Preserva comments rules.*.

    Returns: True si patcheó, False si config.yaml ausente o stacks vacío (no-op).
    """
    import warnings  # noqa: PLC0415

    if not stacks:
        return False

    result = _load_config_for_round_trip(root)
    if result is None:
        warnings.warn(
            f"patch_config_stacks: config.yaml not found at "
            f"{root / 'docs' / 'auditoria' / 'config.yaml'}. No-op.",
            stacklevel=2,
        )
        return False

    yaml, data, config_path = result
    data["context"]["stacks"] = stacks
    _write_config_round_trip(yaml, data, config_path)
    return True


def mark_vision_skipped(root: Path) -> bool:
    """Round-trip ruamel.yaml. Sets context.vision_skipped = True.

    Returns: True si patcheó, False si config.yaml ausente (no-op).
    """
    result = _load_config_for_round_trip(root)
    if result is None:
        return False

    yaml, data, config_path = result
    data["context"]["vision_skipped"] = True
    _write_config_round_trip(yaml, data, config_path)
    return True


def read_overview(root: Path) -> str | None:
    """Read docs/arquitectura/overview.md content if present and non-empty.

    Returns:
        Content as string (UTF-8) if file exists and has non-whitespace content.
        None if file does not exist OR is empty OR whitespace-only.
    """
    overview_path = root / "docs" / "arquitectura" / "overview.md"
    if not overview_path.exists():
        return None
    content = overview_path.read_text(encoding="utf-8")
    if not content.strip():
        return None
    return content


def is_vision_skipped(root: Path) -> bool:
    """Read context.vision_skipped from docs/auditoria/config.yaml.

    Returns:
        True if the flag is explicitly set to True.
        False if config.yaml is missing, malformed, or flag is False/unset.
    """
    import yaml  # noqa: PLC0415

    config_path = root / "docs" / "auditoria" / "config.yaml"
    if not config_path.exists():
        return False
    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return False
    return bool(config.get("context", {}).get("vision_skipped", False))


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


def run(root: Path, mode: str | None = None) -> dict:
    """Run the forge bootstrap process.

    Args:
        root: Project root directory.
        mode: One of 'bootstrap', 'adopt', 'upgrade'. If None, auto-detected via detect_mode().

    Returns a report dict including 'mode' for callers (R-MODE-07).
    """
    if mode is None:
        mode = detect_mode(root)

    report = {
        "project_root": str(root),
        "mode": mode,
        "stacks": [],
        "test_runner": None,
        "dirs_ensured": [],
        "audit_config": None,
        "guardrails_template": None,
        "config_templates": {},
        "codegraph": {"status": None, "warning": None},
        "skill_registry": None,
        "gitignore": None,
        "warnings": [],
    }

    if mode == "bootstrap":
        # Bootstrap: no manifests yet — skip stack detection, mark pending
        stacks = []
        runner, runner_command, detected_from = None, None, ""
        report["warnings"].append(
            "Modo bootstrap: no se detectaron manifiestos. "
            "config.yaml queda con pending_detection: true. "
            "Re-corré /fg-setup o la skill re-detectará el stack cuando aparezcan manifiestos."
        )
        pending_detection = True
        last_detection = None
    else:
        # Adopt / upgrade: run full detection
        stacks = detect_stack(root)
        if not stacks:
            report["warnings"].append("No se detectó un stack reconocido (no hay manifiestos típicos).")

        runner, runner_command, detected_from = detect_test_runner(root, stacks)
        if not runner:
            report["warnings"].append(
                "No se detectó test runner. docs/auditoria/config.yaml queda con test_runner: null. "
                "Si después instalás uno, podés re-correr /fg-setup o editar el config a mano."
            )
        pending_detection = False
        last_detection = datetime.now(timezone.utc).isoformat()

    report["stacks"] = stacks
    report["test_runner"] = (
        {"name": runner, "command": runner_command, "detected_from": detected_from}
        if runner else None
    )

    report["dirs_ensured"] = ensure_dirs(root)
    report["audit_config"] = create_audit_config(
        root, stacks, runner, runner_command, detected_from,
        pending_detection=pending_detection,
        last_detection=last_detection,
    )

    report["guardrails_template"] = create_guardrails_template(root)

    report["config_templates"] = copy_config_templates(root)

    cg_status, cg_warning = init_codegraph(root)
    report["codegraph"] = {"status": cg_status, "warning": cg_warning}
    if cg_warning:
        report["warnings"].append(cg_warning)

    report["skill_registry"] = generate_skill_registry_placeholder(root)
    report["gitignore"] = update_gitignore(root)

    return report


def print_report(report: dict) -> None:
    mode = report.get("mode", "adopt")
    print(f"\nforge inicializado en modo: {mode}")
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


def is_legacy_project(root: Path) -> bool:
    """Detect if project is tagged as legacy.

    Detection paths (OR-semantics):
    1. docs/auditoria/config.yaml -> context.is_legacy == True
    2. docs/arquitectura/overview.md -> YAML frontmatter `legacy: true`

    All other cases (missing files, malformed YAML, false values) -> False.
    Pure function -- no side effects.
    """
    import yaml  # noqa: PLC0415

    # Path 1: config.yaml
    config_path = root / "docs" / "auditoria" / "config.yaml"
    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            if config.get("context", {}).get("is_legacy") is True:
                return True
        except yaml.YAMLError:
            pass

    # Path 2: docs/arquitectura/overview.md frontmatter
    overview_path = root / "docs" / "arquitectura" / "overview.md"
    if not overview_path.exists():
        return False
    try:
        content = overview_path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return False
        end = content.find("---", 3)
        if end == -1:
            return False
        fm = yaml.safe_load(content[3:end]) or {}
        return fm.get("legacy") is True
    except (yaml.YAMLError, OSError):
        return False


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
