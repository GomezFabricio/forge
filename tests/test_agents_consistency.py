"""Tests de consistencia para los agents fg-* (slice C).

Verifica presencia, frontmatter mínimo, paridad command↔agent y no-colisión
con los 6 reviewers. Estos tests son estructurales sobre el árbol del repo:
no dependen del installer ni de mocks — leen los archivos reales.
"""

from pathlib import Path

import yaml

# Raíz del repositorio (dos niveles arriba de tests/)
REPO_ROOT = Path(__file__).parent.parent

AGENTS_DIR = REPO_ROOT / "agents"
COMMANDS_DIR = REPO_ROOT / "commands"

FASES_EXECUTORS = [
    "setup",
    "explore",
    "plan",
    "design",
    "implement",
    "review",
    "update-arch",
]

REVIEWERS = [
    "code-reviewer",
    "dba-reviewer",
    "frontend-reviewer",
    "qa-reviewer",
    "security-reviewer",
    "legacy-impact-analyzer",
]

MODELOS_VALIDOS = {"sonnet", "opus"}


def _parse_frontmatter(path: Path) -> dict:
    """Extrae el bloque YAML frontmatter delimitado por --- de un archivo .md."""
    content = path.read_text(encoding="utf-8")
    parts = content.split("---")
    # parts[0] es vacío (antes del primer ---), parts[1] es el frontmatter
    if len(parts) < 3:
        return {}
    return yaml.safe_load(parts[1]) or {}


class TestPresenciaExecutors:
    """Verifica que los 7 executor agents existan en agents/."""

    def test_todos_los_executors_existen(self):
        """Cada fase debe tener su archivo agents/fg-{fase}.md."""
        faltantes = []
        for fase in FASES_EXECUTORS:
            agent_path = AGENTS_DIR / f"fg-{fase}.md"
            if not agent_path.exists():
                faltantes.append(f"fg-{fase}.md")
        assert faltantes == [], (
            f"Faltan los siguientes executor agents en agents/: {faltantes}"
        )


class TestFrontmatterMinimo:
    """Verifica que cada fg-*.md tenga frontmatter válido con los campos obligatorios."""

    def test_frontmatter_minimo_valido(self):
        """name, description, model válido y tools no vacíos en cada executor."""
        errores = []
        for fase in FASES_EXECUTORS:
            agent_path = AGENTS_DIR / f"fg-{fase}.md"
            if not agent_path.exists():
                errores.append(f"fg-{fase}.md: archivo no existe")
                continue

            fm = _parse_frontmatter(agent_path)
            nombre_esperado = f"fg-{fase}"

            if fm.get("name") != nombre_esperado:
                errores.append(
                    f"fg-{fase}.md: name='{fm.get('name')}' (esperado '{nombre_esperado}')"
                )

            if not fm.get("description"):
                errores.append(f"fg-{fase}.md: description vacío o ausente")

            model = fm.get("model", "")
            if model not in MODELOS_VALIDOS:
                errores.append(
                    f"fg-{fase}.md: model='{model}' (debe ser uno de {MODELOS_VALIDOS})"
                )

            tools = fm.get("tools")
            if not tools:
                errores.append(f"fg-{fase}.md: tools vacío o ausente")

        assert errores == [], "Errores de frontmatter en executor agents:\n" + "\n".join(
            errores
        )


class TestParidadCommandAgent:
    """Verifica paridad 1-a-1 entre commands/fg-*.md y agents/fg-*.md."""

    def test_paridad_command_agent(self):
        """Cada command fg-x debe tener su agent fg-x y viceversa."""
        commands_fg = {
            p.stem for p in COMMANDS_DIR.glob("fg-*.md") if p.is_file()
        }
        agents_fg = {
            p.stem for p in AGENTS_DIR.glob("fg-*.md") if p.is_file()
        }

        sin_agent = sorted(commands_fg - agents_fg)
        sin_command = sorted(agents_fg - commands_fg)

        mensajes = []
        if sin_agent:
            mensajes.append(f"Commands sin agent correspondiente: {sin_agent}")
        if sin_command:
            mensajes.append(f"Agents sin command correspondiente: {sin_command}")

        assert not mensajes, "\n".join(mensajes)


class TestNoColisionConReviewers:
    """Verifica que los basenames de los fg-* y los 6 reviewers sean disjuntos."""

    def test_no_colision_con_reviewers(self):
        """Los nombres de executors fg-* no deben solapar con los reviewers."""
        agents_fg_names = {
            p.stem for p in AGENTS_DIR.glob("fg-*.md") if p.is_file()
        }
        reviewers_names = set(REVIEWERS)

        colision = sorted(agents_fg_names & reviewers_names)
        assert colision == [], (
            f"Colisión de nombres entre executors fg-* y reviewers: {colision}"
        )
