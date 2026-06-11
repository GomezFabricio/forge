"""Tests de consistencia para los agents fg-* (slice C).

Verifica presencia, frontmatter mínimo, paridad command↔agent y no-colisión
con los 6 reviewers. Estos tests son estructurales sobre el árbol del repo:
no dependen del installer ni de mocks — leen los archivos reales.
"""

import re
from pathlib import Path

import yaml

# Raíz del repositorio (dos niveles arriba de tests/)
REPO_ROOT = Path(__file__).parent.parent

AGENTS_DIR = REPO_ROOT / "agents"
COMMANDS_DIR = REPO_ROOT / "commands"
SKILLS_DIR = REPO_ROOT / "skills"
SHARED_SKILLS_DIR = SKILLS_DIR / "_shared"

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

# Canonical skill_resolution enum values (single source: fg-phase-common.md)
CANONICAL_SKILL_RESOLUTION_VALUES = frozenset(
    ["paths-injected", "fallback-registry", "fallback-path", "none"]
)


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


# ---------------------------------------------------------------------------
# Helpers for the new checks
# ---------------------------------------------------------------------------

# Matches full MCP tool names: mcp__<server>__<tool> where the tool part must
# end with a letter or digit (excludes placeholders like codegraph_<tool> or
# codegraph_* where the suffix ends in _ before a non-word char).
_FULL_MCP_TOOL_RE = re.compile(r"\bmcp__[a-z0-9_]+__[a-z0-9][a-z0-9_-]*[a-z0-9]\b")
_ENGRAM_SHORT_RE = re.compile(r"\b(mem_search|mem_get_observation|mem_save)\b")
_BOOTSTRAP_RE = re.compile(r"\bbootstrap\.")
_CODEGRAPH_CLI_RE = re.compile(r"\bcodegraph ")


def _get_skill_text(fase: str) -> str | None:
    """Return the full text of skills/fg-{fase}.md, or None if not found."""
    skill_path = SKILLS_DIR / f"fg-{fase}.md"
    if skill_path.exists():
        return skill_path.read_text(encoding="utf-8")
    return None


def _get_declared_tools(fase: str) -> set[str]:
    """Return the set of tool names declared in agents/fg-{fase}.md frontmatter."""
    agent_path = AGENTS_DIR / f"fg-{fase}.md"
    if not agent_path.exists():
        return set()
    fm = _parse_frontmatter(agent_path)
    tools_raw = fm.get("tools", "")
    if not tools_raw:
        return set()
    return {t.strip() for t in str(tools_raw).split(",") if t.strip()}


class TestDeclaredToolsSuperset:
    """(a) Verifica que las tools declaradas en cada fg-*.md agent sean ⊇ las invocadas
    en el skill correspondiente.

    Reglas de chequeo:
    - Cada tool MCP completa mencionada en el texto de la skill (patrón
      mcp__<server>__<tool>) debe aparecer en el tools: del agent.
    - Los short names de engram (mem_search, mem_get_observation, mem_save) se
      verifican prefix-agnostic: el agent debe tener una tool que TERMINE en ese
      nombre (ej: mcp__engram__mem_save satisface mem_save).
    - Si el texto de la skill contiene bootstrap. o "codegraph " (CLI), el agent
      debe declarar Bash.
    - La verificación de Bash también aplica a TODOS los executors fg-* porque
      fg-phase-common.md Sección A obliga el GATE de re-detección lazy
      (forge.bootstrap.needs_detection) en todas las skills. Esto se verifica
      individualmente con la heurística del skill, no como blanket assertion,
      porque lo que cuenta es que la evidencia esté en el skill o en fg-phase-common.
      Dado que fg-phase-common.md menciona bootstrap. y es cargado por todos los
      executors, todos deben tener Bash — se valida en un test separado.
    - Over-declaring es inofensivo: no se falla si el agent declara más tools de
      las que menciona el skill.
    - No se hace excepción especial para tool names en warnings/negaciones: si el
      skill nombra un MCP tool, el agent debe poder usarlo (over-declaring es seguro).
    """

    def test_declared_tools_superset_of_invoked(self):
        errores = []
        for fase in FASES_EXECUTORS:
            skill_text = _get_skill_text(fase)
            if skill_text is None:
                continue
            declared = _get_declared_tools(fase)
            declared_lower = {t.lower() for t in declared}

            # Check full MCP tool names mentioned in skill text
            invoked_mcp = set(_FULL_MCP_TOOL_RE.findall(skill_text))
            for tool in invoked_mcp:
                if tool not in declared:
                    errores.append(
                        f"fg-{fase}: skill menciona '{tool}' pero no está en tools:"
                    )

            # Check engram short names (prefix-agnostic)
            invoked_short = set(_ENGRAM_SHORT_RE.findall(skill_text))
            for short in invoked_short:
                if not any(t.endswith(short) for t in declared):
                    errores.append(
                        f"fg-{fase}: skill menciona '{short}' pero ninguna tool en"
                        f" tools: termina en '{short}'"
                    )

            # Check Bash requirement from skill-specific heuristics
            needs_bash = bool(
                _BOOTSTRAP_RE.search(skill_text) or _CODEGRAPH_CLI_RE.search(skill_text)
            )
            if needs_bash and "Bash" not in declared:
                errores.append(
                    f"fg-{fase}: skill usa bootstrap. o CLI 'codegraph' pero no"
                    f" declara Bash en tools:"
                )

        assert errores == [], (
            "Herramientas invocadas en skills sin declarar en agent tools:\n"
            + "\n".join(errores)
        )

    def test_all_executors_declare_bash(self):
        """Todos los executors fg-* deben declarar Bash.

        fg-phase-common.md Sección A obliga el GATE de re-detección lazy
        (forge.bootstrap.needs_detection) en TODAS las skills fg-*. Dado que ese
        módulo compartido usa bootstrap. y todos los executors lo cargan, todos
        requieren Bash. Si un executor no lo tiene, es una omisión.
        """
        # Verify the premise: fg-phase-common.md does contain bootstrap.
        phase_common = (SHARED_SKILLS_DIR / "fg-phase-common.md").read_text(
            encoding="utf-8"
        )
        assert _BOOTSTRAP_RE.search(phase_common), (
            "fg-phase-common.md ya no menciona bootstrap. — revisar si la"
            " regla del blanket Bash assertion sigue siendo válida"
        )

        faltantes = []
        for fase in FASES_EXECUTORS:
            declared = _get_declared_tools(fase)
            if "Bash" not in declared:
                faltantes.append(f"fg-{fase}")

        assert faltantes == [], (
            f"Executors sin Bash (requerido por fg-phase-common Sección A): {faltantes}"
        )


class TestSkillResolutionEnumSingleSource:
    """(b) Verifica que el enum skill_resolution use fg-phase-common como única fuente.

    Checks:
    - El enum canónico en fg-phase-common.md es exactamente los 4 valores
      esperados: {paths-injected, fallback-registry, fallback-path, none}.
    - Cada skill fg-*.md que define skill_resolution en su envelope sólo usa
      valores de ese conjunto.
    - skill-resolver.md NO contiene el valor legacy 'injected' como entrada
      standalone del enum (paths-injected contiene 'injected' como substring,
      el check distingue el valor exacto delimitado por backtick/pipe/espacio).
    """

    def _parse_skill_resolution_values(self, text: str) -> set[str]:
        """Extract values listed after 'skill_resolution:' in a YAML code block."""
        # Match lines like: skill_resolution: val1 | val2 | val3
        match = re.search(r"skill_resolution:\s+([^\n]+)", text)
        if not match:
            return set()
        raw = match.group(1)
        # Split on | and strip whitespace
        return {v.strip() for v in raw.split("|") if v.strip()}

    def test_canonical_enum_in_phase_common(self):
        """fg-phase-common.md define exactamente los 4 valores canónicos."""
        phase_common_text = (SHARED_SKILLS_DIR / "fg-phase-common.md").read_text(
            encoding="utf-8"
        )
        found = self._parse_skill_resolution_values(phase_common_text)
        assert found == CANONICAL_SKILL_RESOLUTION_VALUES, (
            f"fg-phase-common.md skill_resolution values: {found}\n"
            f"Esperado: {CANONICAL_SKILL_RESOLUTION_VALUES}"
        )

    def test_skills_use_only_canonical_values(self):
        """Cada skill fg-*.md usa sólo los valores canónicos de skill_resolution."""
        errores = []
        for skill_path in sorted(SKILLS_DIR.glob("fg-*.md")):
            text = skill_path.read_text(encoding="utf-8")
            values = self._parse_skill_resolution_values(text)
            if not values:
                continue
            invalid = values - CANONICAL_SKILL_RESOLUTION_VALUES
            if invalid:
                errores.append(
                    f"{skill_path.name}: valores no canónicos en skill_resolution:"
                    f" {sorted(invalid)}"
                )
        assert errores == [], "\n".join(errores)

    def test_skill_resolver_no_legacy_injected_value(self):
        """skill-resolver.md no debe contener 'injected' como valor standalone del enum.

        El valor legacy era `injected`; el canónico es `paths-injected`.
        paths-injected contiene 'injected' como substring, así que la búsqueda
        excluye ocurrencias donde 'injected' está precedido por 'paths-'.
        """
        resolver_text = (SHARED_SKILLS_DIR / "skill-resolver.md").read_text(
            encoding="utf-8"
        )
        # Find backtick-quoted values: `injected` (not `paths-injected`)
        # Pattern: backtick, optional word boundary, 'injected', backtick
        # but NOT if preceded by 'paths-'
        standalone_injected = re.findall(r"`(?<!paths-)injected`", resolver_text)
        # Also check pipe-delimited enum lines (e.g.: injected | fallback-registry)
        # Extract skill_resolution enum line values
        enum_values = self._parse_skill_resolution_values(resolver_text)
        has_bare_injected = "injected" in enum_values

        assert not standalone_injected and not has_bare_injected, (
            "skill-resolver.md contiene el valor legacy 'injected' (sin prefijo"
            " 'paths-'). Debe ser 'paths-injected'.\n"
            f"  Ocurrencias backtick: {standalone_injected}\n"
            f"  En enum: {has_bare_injected}"
        )
