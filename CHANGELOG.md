# Changelog

Todas las modificaciones relevantes de **forge** quedan documentadas en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

> **Política pre-1.0**: la serie `0.x` indica "pre-estable" — la API y el comportamiento pueden cambiar sin previo aviso entre versiones menores. Se llegará a `v1.0.0` cuando el primer piloto cierre con éxito.

## [Unreleased]

### Perfiles de modelo por fase (`model_profile`)

#### Added

- **El modelo de cada fase ahora es configurable vía perfil.** Nuevo `rules.workflow.model_profile` en `docs/auditoria/config.yaml`, con tres opciones: `equilibrado` (default — `opus` en plan/design/review, `sonnet` en los executors; = comportamiento previo), `performance` (`opus` en todas las fases) y `basico` (`sonnet` en plan/design/review, `haiku` en los executors). El orquestador lee el perfil y le pasa el modelo correspondiente a cada agente `fg-*` al delegar; el frontmatter `model:` de cada agente queda como red de seguridad (el default `equilibrado`). Documentado en `templates/CLAUDE-md-institucional.md` → "Modelos por fase — perfiles configurables". forge no usa ni referencia el modelo Fable en ningún perfil.

### Instalación — CodeGraph (bundle completo) y filtro PII (modelo spaCy)

#### Fixed

- **`install_codegraph()` extraía solo el wrapper, no el bundle.** El release de CodeGraph no es un binario estático sino un bundle (`node` + `bin/codegraph` + `lib/dist/bin/codegraph.js`); el instalador extraía únicamente el wrapper y lo dejaba huérfano (`codegraph --version` → "No such file or directory", pese a reportar "instalado"). Ahora extrae el árbol completo a `~/.codegraph/` strippeando el directorio top-level, hace `chmod +x` del wrapper **y** del `node` bundleado, corre el cleanup de quarantine de macOS de forma **recursiva** (el quarantine sobre `node` también bloquea la ejecución), y valida estructuralmente (wrapper + runtime `node` presentes) fallando ruidoso si el bundle quedó incompleto. Ramas `.tar.gz` y `.zip`.
- **El hook PII no redactaba nada y crasheaba el prompt.** `build_analyzer()` pasaba `nlp_engine=None`, lo que hacía que Presidio cayera a su modelo default `en_core_web_lg`, no lo encontrara e intentara autodescargarlo en runtime → `sys.exit()` (un `SystemExit` que el fail-open `except Exception` del hook no atrapaba) → exit 1 con el error de spaCy en stdout, sin redactar (PII iba sin filtrar a la API). Ahora se usa un `SpacyNlpEngine` explícito con `en_core_web_sm` (~12MB, declarado como dependencia directa en `pyproject.toml` para que pipx/pip lo depositen en el venv) que **nunca** autodescarga: un modelo ausente se vuelve un `OSError` que el fail-open sí atrapa. El modelo es necesario porque Presidio siempre tokeniza y la detección de secretos por contexto (AWS/OpenAI/Bearer) depende de los lemas.

#### Added

- **Smoke-check del filtro PII al final de `forge install`**: tras registrar el hook, construye el analyzer y corre una redacción de prueba; si falla, el reporte avisa ruidosamente (estado `registered_broken`) en vez de declarar "registrado" sobre un filtro que dejaría pasar PII en silencio (fail-open).
- **Los instaladores guían la instalación de Python cuando falta.** `install.sh` e `install.ps1` ya no abortan con un escueto "instalalo y volvé a correr": detectan el SO/gestor de paquetes y muestran el **comando exacto** (`brew install python@3.13`, `sudo apt install …`, `dnf`, `pacman`, `zypper`, `winget install Python.Python.3.13` o el instalador de python.org), avisan del stub de Microsoft Store en Windows, y recuerdan re-correr el instalador. No instalan Python por su cuenta (decisión explícita del usuario).
- **El filtro PII detecta secretos descritos en español.** `AWS_SECRET_KEY` y `OPENAI_KEY` (los recognizers que dependen de contexto) suman pistas en español a sus listas (`clave`, `secreto/a`, `credencial`, `contraseña`, `aws`), además de las inglesas/identificador. Así "mi clave secreta de aws es …" dispara la redacción, no solo `AWS_SECRET_ACCESS_KEY=…`. Como el modelo spaCy es inglés y no lematiza el español a su raíz, se listan las formas de superficie (con y sin tilde). `BEARER_TOKEN` y `CONNECTION_STRING_PASSWORD` ya firaban sin contexto en cualquier idioma.

#### Changed

- **`templates/CLAUDE-md-institucional.md`**: nueva subsección "Precedencia al recibir un cambio (y repo sin scaffolding)" — forge está siempre activo; ante un cambio sobre nivel Libre con `config.yaml` ausente, `/fg-setup` es el paso cero antes del ciclo SDD. Un PRD o un diseño previo alimenta las fases, no las reemplaza.

### Modelo de interacción — los executors no preguntan al dev, el orquestador resuelve

#### Changed

- **Las skills `fg-*` ya no le preguntan al dev de forma inline.** Un sub-agente no puede usar `AskUserQuestion` ni prompts interactivos (restricción de Claude Code), así que las fases reportan las decisiones como dato y el **orquestador** las resuelve. Nuevo campo `decisions_needed` en el envelope (`skills/_shared/fg-phase-common.md`, Sección B.1); el orquestador pregunta —con `AskUserQuestion` cuando las opciones son discretas— y re-invoca la fase con la respuesta resuelta. Alinea forge con el patrón de SDD (los executors reportan blockers, el orquestador interactúa).
- **`fg-setup`**: la conversación de visión (bootstrap) la conduce ahora el orquestador. La fase devuelve `vision_status: pending-orchestrator` y, en la re-invocación, escribe `overview.md`/`stack.md` desde el contenido aceptado. git init, manifiesto polyglot y CodeGraph degradado pasan por `decisions_needed`.
- **`fg-plan`**: ambigüedad de tipo/nombre y clarificación de scope → `decisions_needed`.
- **`fg-design`**: cambio activo, estrategia de migración legacy, `size:exception`, decisiones técnicas no obvias y re-correr/sobrescribir → `decisions_needed`.
- **`fg-review`**: severidad/scope ambiguos → `decisions_needed`.
- **`fg-update-arch`**: las propuestas de ADR se devuelven como lista de datos (`proposals`); el orquestador itera la aprobación (aceptar/editar/rechazar con `AskUserQuestion`) y re-invoca con `proposal_decisions` para aplicar.
- **`templates/CLAUDE-md-institucional.md`**: doctrina del orquestador como dueño de la interacción + los dos patrones multi-turno (conversación guiada, aprobación multi-ítem).

#### Fixed

- **Inconsistencias de documentación en las skills**: `fg-setup.md` ahora documenta que deposita `docs/auditoria/guardrails.yaml`; `fg-implement.md` condiciona la escritura de `evidencia-tdd.md` a Strict TDD activo (antes la prosa y el envelope se contradecían). Eliminado el archivo huérfano `.forge/redactions.jsonl`.

### D12 + P1 — Nueva fase /fg-update-registry y skill-resolver reescrito al modelo índice/paths

#### Added

- **Nueva fase `/fg-update-registry`** (`commands/fg-update-registry.md`, `agents/fg-update-registry.md`,
  `skills/fg-update-registry.md`): genera o regenera `.atl/skill-registry.md` como índice de skills del
  proyecto. Escanea `skills/` del proyecto y `~/.claude/skills/` del usuario; lee solo el frontmatter
  de cada `SKILL.md`; deduplica por nombre (project beats user); excluye `fg-*`, `sdd-*`, `_shared`,
  `forge-shared` y `skill-registry`. Escribe la tabla de índice (nombre, trigger/descripción, scope,
  path exacto) y persiste en engram con `topic_key: skill-registry`. El orquestador lo invoca después
  de `/fg-setup` y cada vez que se instalan, crean, mueven o renombran skills.
- **`.atl/` agregado a `.gitignore`** por `bootstrap.update_gitignore()`: el registry es un artefacto
  regenerable, no se versiona.

#### Changed

- **`skills/_shared/skill-resolver.md` reescrito al modelo índice/paths**: el Paso 3 ahora pasa los
  paths exactos de `SKILL.md` bajo `## Skills to load before work` en lugar de inyectar compact rules
  pre-digeridas. El registry es un índice — `SKILL.md` sigue siendo la fuente de verdad. Los sub-agentes
  leen los archivos completos preservando el intent del autor. El feedback-loop enum permanece idéntico
  (`paths-injected | fallback-registry | fallback-path | none`). Aviso de registry ausente actualizado
  a `/fg-update-registry`. Sección de presupuesto de tokens reescrita honestamente: ~1 línea por path
  en el orquestador; el costo real está en el contexto del sub-agente (que es el punto).
- **`/fg-setup` paso 8** y envelope: el paso solo escribe el placeholder; el registry real lo genera
  el orquestador invocando `/fg-update-registry` después del setup. `next_recommended` apunta a
  `/fg-update-registry`.
- **Conteos actualizados**: de 7 a 8 skills, de 7 a 8 commands, de 13 a 14 agentes en README,
  `docs/guia-de-uso.md`, `CONTRIBUTING.md`, `templates/CLAUDE-md-institucional.md`,
  `forge/installer.py` y `.github/scripts/verify_install.py`.
- **`tests/test_agents_consistency.py`**: `FASES_EXECUTORS` actualizado a 8 fases (agregado
  `update-registry`); docstring de clase actualizado.

---

### P3, P5 y D10 — Protocolo de re-ejecución, defensa en profundidad y fix de wheel

#### Added

- **Re-ejecución acotada tras review bloqueante** (P3, `templates/CLAUDE-md-institucional.md`,
  `skills/fg-review.md`): protocolo formal para `verdict: blocking` — el orquestador
  re-invoca `/fg-implement` con los issues estructurados de los reviewers como contexto,
  re-corre `/fg-review`, máximo 2 reintentos y luego escala al dev. Cada reintento se
  registra en `decisiones.md` (append-only). No aplica a `issues_found` (no bloqueante).
  La skill reporta; el orquestador decide — la separación executor/orquestador se preserva.
- **Sección "Defensa en profundidad"** (P5, `README.md`, `docs/guia-de-uso.md`): mapa de
  las 4 capas de enforcement reales — hook PII (entrada), guardrails PreToolUse
  (ejecución), `/fg-review` + reviewers (juicio LLM) y tests de consistencia en CI
  (contratos del propio repo) — con mecanismo, ubicación y kill-switch de cada una.

#### Fixed

- **`PACKAGE_ROOT` en instalaciones wheel non-editable** (D10, `forge/bootstrap.py`):
  `_resolve_package_root()` resuelve la raíz de recursos verificando la existencia de
  `config/` en dos layouts — repo/editable (`Path(__file__).parent.parent`) y wheel
  (`sysconfig data_dir/share/forge`, la misma resolución que `installer.get_share_root()`).
  Antes, `copy_config_templates()` fallaba con `FileNotFoundError` en wheels non-editable.

---

### P2 — Hook PreToolUse de guardrails

Capa de enforcement determinista que intercepta comandos Bash antes de ejecución
y bloquea/pide confirmación para operaciones declaradas en `docs/auditoria/guardrails.yaml`.
Endurece la regla operativa 8 ("authorize-first en operaciones destructivas"), que antes
era solo instrucción de prompt.

#### Added

- **`forge/guards/hook_pre_tool.py`** — nuevo hook `PreToolUse` que evalúa reglas de
  `docs/auditoria/guardrails.yaml`. Acciones `block` (deny) y `confirm` (ask). Fail-open:
  cualquier error interno → `{}` y exit 0. Kill-switch `FORGE_GUARD_DISABLE`.
- **`templates/guardrails.yaml`** — plantilla comentada en español con reglas sensatas por
  defecto: `git push --force`, `git reset --hard`, `git clean -f`, `git checkout -- .`,
  `rm -rf`, `docker compose down -v`, `DROP TABLE/DATABASE`.
- **`forge/bootstrap.py` `create_guardrails_template()`** — deposita la plantilla en
  `docs/auditoria/guardrails.yaml` (no-overwrite, idempotente). Wired into `run()`.
- **`forge install --skip-guard-hook`** — omite el auto-registro del hook de guardrails.
- **Log `.forge/auditoria-guard.jsonl`** — decisiones y errores del hook, append-only JSONL.
  No contiene el comando completo, solo SHA-256[:16] para correlación.

---

### Fase 3 — Correcciones de arquitectura (D16, D18, D2, D8, D11)

Cierra las discrepancias de arquitectura detectadas en el documento de exploración
exhaustiva: registro MCP de engram corregido, límites del filtro PII documentados,
y propiedad del `cycle_mode` migrada al orquestador.

#### Added

- **Documentación de límites del filtro PII** (`README.md`, `docs/guia-de-uso.md`): nueva
  sección "Límites conocidos del filtro PII" con tres trade-offs explícitos: (D2) política
  fail-open ante crash del hook (el prompt pasa sin redactar — ADR-4, intencional, distinto
  a `FORGE_PII_DISABLE`); (D8) sobre-redacción de cadenas de conexión (el segmento
  completo `protocolo://usuario:contraseña@` se redacta, no solo la contraseña — limitación
  de Presidio sin reemplazo parcial, seguro por diseño); (D11) log de auditoría sin rotación
  automática (append-only, ~150-200 bytes por evento, gestión manual por el dev, nunca
  contiene texto del prompt).

#### Changed

- **Registro MCP de engram migrado a `~/.claude.json`** (D18, `forge/installer.py`):
  `register_mcp()` reemplazado por `register_engram_mcp()`, que escribe
  `mcpServers.engram` en `~/.claude.json` con el mismo patrón merge + backup `.forge-bak`
  que CodeGraph y Context7. El command es la ruta absoluta al binario cuando el instalador
  la conoce (más robusto que depender del PATH para MCP spawning), o `"engram"` como
  fallback. Eliminado el mecanismo muerto `MCP_JSON_PATH` / `~/.claude/mcp/engram.json`
  (formato flat que Claude Code nunca leyó). `detect_engram()` indicador 1 actualizado:
  ya no lee el JSON flat, ahora verifica `mcpServers.engram` en `~/.claude.json`.
  Tests actualizados: `TestRegisterEngramMcp` (idempotencia, merge, backup, ruta absoluta
  vs fallback), `TestDetectEngram` (nuevo mecanismo + short-circuit). (`tests/test_installer.py`)

- **`cycle_mode` preguntado por el orquestador** (D16, `templates/CLAUDE-md-institucional.md`,
  `skills/_shared/fg-phase-common.md`, `README.md`, `docs/guia-de-uso.md`): la doctrina y
  los docs ahora atribuyen correctamente la pregunta de modo interactivo/automático al
  orquestador (antes del primer ciclo SDD de la sesión), no a `/fg-plan`. El campo
  `cycle_mode` fue removido del envelope de `/fg-plan`. `rules.workflow.cycle_mode` en
  `config.yaml` sigue siendo la fuente del valor pre-seleccionado.

---

### Fase 2 — Contratos agents-skills y correcciones de infraestructura (D1, D3, D13, D14, D15)

Correcciones mecánicas detectadas durante la exploración del repo: prefijos de tools de
engram, enum `skill_resolution`, kill-switch PII, log de errores del hook PII, y test
de consistencia estructural.

#### Added

- **Test de consistencia estructural** (`tests/test_agents_consistency.py`): valida que
  los agents declaren exactamente las tools que los skills de los que dependen requieren;
  detecta automáticamente drift entre capas sin necesidad de revisión manual.

#### Fixed

- **Prefijos de tools de engram corregidos a `mcp__engram__*`** (D14, `agents/`): los
  executors `fg-plan`, `fg-design`, `fg-implement`, `fg-review`, `fg-explore`, `fg-setup`
  y el agent de actualización de arquitectura usaban prefijos incorrectos; corregidos al
  prefijo real del MCP server de engram.
- **`skill_resolution` unificado** (D15, `skills/_shared/fg-phase-common.md`): enum
  declarado como fuente canónica; todos los skills que listan el campo ahora usan
  exactamente los cuatro valores válidos.
- **`FORGE_PII_DISABLE` real** (D3, `forge/filters/hook_user_prompt.py`): la variable de
  entorno ya detiene el filtro correctamente (antes la implementación no la chequeaba).
- **`action: "error"` en el log de auditoría PII** (D1): el hook ahora registra un evento
  de error en `.forge/auditoria-pii.jsonl` cuando el filtro falla, en lugar de silenciar
  la excepción sin traza.

---

### Doctrina del orquestador global — el CLAUDE.md institucional pasa a `~/.claude/`

> **CAMBIO DE ARQUITECTURA**: la doctrina del orquestador (persona, gradación de ceremonia,
> modelo de delegación, model assignments, reglas de engram) deja de ser per-proyecto y pasa a ser
> **global**. forge ya no asume un orquestador externo: lo aporta él. Cierra el agujero que dejó el
> slice E (al retirar `inject_orchestrator_rule` sin reemplazo, una instalación limpia quedaba sin
> cerebro de orquestador global hasta correr `/fg-setup` en un proyecto).

#### Added

- **`install_global_claude_md()`** (`forge/installer.py`): `forge install` instala el institucional
  como `~/.claude/CLAUDE.md`. Idempotente: si el global ya es byte-idéntico no hace nada; si difiere,
  respalda el previo en `~/.claude/backup/forge/<timestamp>/` antes de pisarlo (fuera del path de
  carga de Claude Code, para no confundir al modelo con dos CLAUDE.md). Wireado en `run()` fail-open.
  Tests: `TestInstallGlobalClaudeMd`, `TestRunGlobalClaudeMd`.

#### Changed

- **`templates/CLAUDE-md-institucional.md`**: reescrito de voz "proyecto" a voz "global". Aclara que
  el comportamiento per-proyecto (TDD, test runner, ceremonia, PR size, legacy) se lee de
  `docs/auditoria/config.yaml`, y que las reglas propias de un proyecto van en el `CLAUDE.md` de ese
  repo (del dev, forge no lo toca).
- **`forge/bootstrap.py` / `/fg-setup`**: dejan de generar/mergear el `CLAUDE.md` del proyecto.
  Retirados `merge_or_create_claude_md` y `extract_section` (y sus tests). `/fg-setup` sigue generando
  `config.yaml`, inicializando CodeGraph y el skill-registry.
- **Docs y skills**: README, guía y los `fg-setup` (skill/command/agent) reflejan que la doctrina es
  global y que `/fg-setup` ya no escribe `CLAUDE.md`.

---

### Instalación sin fricción — auto-registro del hook PII + scripts de instalación

Cierra las dos brechas que faltaban para una instalación "de un comando": el hook de
redacción PII ahora se registra solo durante `forge install`, y existen scripts de
instalación para las tres plataformas.

#### Added

- **Auto-registro del hook PII** (`forge/installer.py`): `register_pii_hook()` mergea de
  forma idempotente el hook `UserPromptSubmit` en `~/.claude/settings.json`, preservando
  los hooks existentes y creando backup `.forge-bak` antes de escribir. El comando se ancla
  a `sys.executable` (el intérprete del venv de pipx donde quedó forge), no a un `python`
  genérico del PATH que no tendría forge importable. Wireado en `run()` con política
  fail-open: un fallo del registro no aborta la instalación ni cambia el exit code.
- **Flag `--skip-pii-hook`** (`forge/cli.py`): omite el auto-registro del hook PII.
- **Scripts de instalación** (`install.sh`, `install.ps1`): vía rápida de un comando
  (`curl … | bash`, `iwr … | iex`). Verifican Python 3.10+, aseguran `pipx` (con fallback
  `--break-system-packages` para entornos PEP 668), instalan forge aislado con
  `pipx install --force` y corren `forge install`. Los argumentos extra se reenvían tal cual.
- **`.gitattributes`**: fuerza fin de línea LF en `*.sh` para que `install.sh` no se corrompa
  al clonar en Windows (CRLF rompe el shebang bajo bash).
- **Tests** (`tests/test_installer.py`, `tests/test_cli.py`): `TestRegisterPiiHook`,
  `TestRunPiiHook` y tests del flag `--skip-pii-hook`, en ciclo Strict TDD RED→GREEN.

#### Fixed

- **Aislamiento de tests (CC-NO-REAL-HOME)**: fixture autouse `_isolate_claude_home` en
  `tests/test_installer.py` que redirige `CLAUDE_HOME` y `CODEGRAPH_CLAUDE_JSON` a `tmp`.
  Los tests de `run()` (`TestRun`, `TestRunAdditional`, `TestRunCodegraph`, `TestRunContext7`)
  invocaban los registrars reales contra el `~/.claude` del usuario, violando la constraint
  declarada del módulo de tests.

#### Changed

- **`README.md`** y **`docs/guia-de-uso.md`**: los scripts de instalación dejan de figurar
  como pendientes; documentados la matriz de compatibilidad (Windows/macOS/Linux), los
  prerequisitos, el paso a paso y el auto-registro del hook PII.

---

### Retiro del mecanismo de inyección de orquestador — Slice E (arq-orchestrator-rule-completo)

> **NOTA DE RETIRO**: `forge/templates/orchestrator-rule.md` eliminado del repositorio: era
> un archivo huérfano (vivía en `forge/templates/` pero el installer lo buscaba en `templates/`
> raíz, por lo que nunca llegó a desplegarse en producción). La doctrina de orquestación se
> consolida en `templates/CLAUDE-md-institucional.md`, que incluye el modelo de 3 capas,
> la tabla de model assignments y el sub-agent context protocol.

#### Removed

- **`forge/templates/orchestrator-rule.md`** — retirado. Era huérfano: el installer lo buscaba
  en una ruta distinta y el bloque `<!-- forge:orchestrator -->` nunca se inyectó en
  instalaciones reales. El contenido de gradación ya estaba duplicado en
  `templates/CLAUDE-md-institucional.md`.
- **`inject_orchestrator_rule()`** — retirado de `forge/installer.py`. El paso era silencioso
  (el template no existía en la ruta esperada). `forge install` completa sin ese paso, sin
  cambio observable para los usuarios.
- **`TestInjectOrchestratorRule`** y los 15 patches de `inject_orchestrator_rule` en
  `tests/test_installer.py` — retirados junto con la función.

#### Changed

- **`templates/CLAUDE-md-institucional.md`**: sección "Modelo de delegación" reescrita para
  describir las 3 capas del modelo de orquestación (commands → agents → skills), con tabla
  de model assignments (`fg-plan`/`fg-design`/`fg-review` = opus; resto = sonnet) y sub-agent
  context protocol (skill path, engram topic keys, strict-tdd forwarding). Referencias rotas
  a `orchestrator-rule.md` eliminadas; patrón Grep de verificación de arquitectura inlineado.

---

### Desacoplamiento de orquestación — Slice A (arq-desacoplar-orquestacion)

> **NOTA DE DEPRECACIÓN**: `forge/portero_decision.py` y `forge/arch_freshness.py` fueron
> retirados del repositorio. La decisión de nivel de ceremonia (Libre/Rápido/Completo) pasa
> a ser juicio del orquestador (Claude) guiado por las reglas declarativas en
> `forge/templates/orchestrator-rule.md`. No se crea código Python de reemplazo.
> Las entradas históricas que documentan estos módulos se conservan más abajo.

#### Removed

- **`forge/portero_decision.py`** — retirado. La función `decidir_nivel` ya no existe como código Python. La doctrina de precedencia de señales vive en `forge/templates/orchestrator-rule.md` (tabla de precedencia + regla conservadora + detección de arquitectura al día vía Grep).
- **`forge/arch_freshness.py`** — retirado. La detección de "arquitectura al día" pasa a un Grep declarativo del orquestador sobre `docs/auditoria/cambios/*/README.md` (frontmatter `structural`/`arch_synced`), documentado en `orchestrator-rule.md`.
- **`tests/test_portero_decision.py`** y **`tests/test_arch_freshness.py`** — retirados junto con sus módulos.

#### Changed

- **`forge/templates/orchestrator-rule.md`**: reforzado con tabla de precedencia explícita de 4 señales (`ceremonial_threshold > opt-in > tipo > palabras_de_escala`), regla de detección de arquitectura al día vía Grep (3 pasos), y eliminación de referencias al portero como componente de código.
- **`skills/fg-plan.md`**: eliminados pasos 0 (modo de ciclo) y 0.5 (portero proporcional). La skill arranca directamente en la inferencia del tipo. El nivel de ceremonia llega ya resuelto desde el orquestador.
- **`skills/fg-explore.md`**: liberado como fase 0 independiente. El gate de avance pasa de "debe existir README.md" a "debe existir la carpeta del cambio". El Context7 gate (paso 4.5) re-anclado al nivel determinado por el orquestador (no por el portero).

---

### Portero proporcional (Fase 1 — histórico)

Implementa el portero de ceremonia proporcional: antes de iniciar un cambio, el workflow evalúa
señales del contexto y propone el nivel de ritual mínimo adecuado (Libre / Rápido / Completo).
El dev confirma o ajusta; forge nunca impone el nivel sin consentimiento explícito.

#### Added

- **`forge/portero_decision.py`** — función pura `decidir_nivel(senales)` que aplica la precedencia
  de señales (threshold → opt-in → tipo → palabras de escala → regla conservadora) y retorna
  `nivel_propuesto`, `razon` y `confianza`. Sin I/O, 100% testeable.
- **`forge/arch_freshness.py`** — función `check_arch_freshness(cambios_dir, arch_overview)` que
  escanea los READMEs de cambios buscando `structural: true` sin `arch_synced: true` y reporta
  `al_dia`, `pendientes` y `sin_overview`.
- **Campo `rules.workflow.ceremonial_threshold`** en `docs/auditoria/config.yaml` (valores:
  `auto` / `lite` / `full`; default `auto`). Controla el sesgo del portero a nivel de proyecto.
- **`templates/tareas-lite.md`** — template de tareas reducido para modo Rápido (sin sección de
  diseño técnico ni decisiones estructurales; mantiene el checklist básico de implementación).
- **Paso 0.5 en `skills/fg-plan.md`** — el portero se ejecuta entre la resolución del modo de
  ciclo (paso 0) y la inferencia del tipo (paso 1). Incluye las 5 señales de evaluación, la
  lógica UX propone-y-confirma, y el cacheo del `ceremony_level` en el envelope de retorno.
- **Niveles de ceremonia**:
  - **Libre** — forge no entra al ciclo; el dev trabaja sin estructura impuesta.
  - **Rápido** — saltea solo `/fg-design`; `/fg-review` siempre corre (R-PORTERO-02).
  - **Completo** — ritual completo, sin cambios respecto al flujo estándar.

#### Fixed

- **F811 eliminado** (`forge/arch_freshness.py`): redefinición de variable local que generaba
  warning de Ruff; reescrita la sección afectada con nombre de variable único.
- **Parser de frontmatter migrado a `yaml.safe_load`** (`forge/arch_freshness.py`): el parser
  anterior usaba `yaml.load()` sin `Loader`, disparando el warning de seguridad `YAMLLoadWarning`.
  Migrado a `yaml.safe_load()` con manejo explícito de `yaml.YAMLError`.

---

### Modelo de activación latente

Implementa el PRD `.forge/prd-activacion-latente.md`: forge se vuelve latente e
invocable por intent natural en lugar de comando explícito.

### Added

- **`forge install` implementado** (`forge/installer.py`, ~270 LOC): depósito de skills, agents y registro de MCP de engram en `~/.claude/`. Incluye detección automática de engram (3 indicadores), prompt Y/N interactivo, flag `--install-engram` (non-interactive), flag `--skip-engram-check`, e idempotencia completa.
- **Auto-install de engram**: descarga el binario desde GitHub Releases (`engram_{version}_{os}_{arch}.tar.gz|.zip`), extrae el binario, aplica `chmod +x` (Unix), limpia quarantine en macOS, edita `~/.profile` (Unix) o `HKCU\Environment\Path` (Windows). *(El registro MCP original usaba `~/.claude/mcp/engram.json` schema flat — migrado a `~/.claude.json` `mcpServers.engram` en D18; ver [Unreleased].)*
- **Deposit de skills con transformación de layout**: `fg-*.md` → `~/.claude/skills/<stem>/SKILL.md`; co-located companions (`strict-tdd.md`, `strict-tdd-verify.md`) depositados junto a su skill consumidora; archivos cross-cutting (`skill-resolver`, `engram-protocol`, `fg-phase-common`) → `~/.claude/skills/forge-shared/<name>/SKILL.md` con frontmatter `disable-model-invocation: true` inyectado.
- **Exit codes claros**: `EXIT_OK=0`, `EXIT_ABORTED=10`, `EXIT_ENGRAM_INSTALL_FAILED=20`, `EXIT_DEPOSIT_FAILED=30`, `EXIT_PLATFORM_UNSUPPORTED=40`.
- **Test suite** (`tests/test_installer.py`, `tests/test_cli.py`): 201 tests nuevos, cobertura ≥88% sobre `forge/installer.py` y 100% sobre `forge/cli.py` modificado. Strict TDD ciclo RED→GREEN→TRIANGULATE→REFACTOR por tarea.
- **Inyección de regla `<!-- forge:orchestrator -->`** en `~/.claude/CLAUDE.md` global desde `forge install` (#13).
- **`bootstrap.detect_mode(root)`** devuelve `bootstrap | adopt | upgrade` según estado del directorio (#16).
- **Lazy detection de stack/test_runner**: `bootstrap.needs_detection` + `bootstrap.update_detection_fields` para re-detección post-`/fg-setup` (#16).
- **GATE de lazy detection** en `_shared/fg-phase-common.md` Sección A — fuerza re-detección cuando `pending_detection: true` (#16).
- **`/fg-setup` modo bootstrap**: dispara conversación de visión del sistema y produce `docs/arquitectura/overview.md` + `stack.md` antes del primer código (#17).
- **Helpers de bootstrap para modo greenfield**: `bootstrap.create_arquitectura_docs`, `bootstrap.patch_config_stacks`, `bootstrap.mark_vision_skipped`, `bootstrap.read_overview`, `bootstrap.is_vision_skipped`, `bootstrap.is_legacy_project` (#17, #18, #19).
- **`/fg-plan` lee `overview.md`** como contexto primario via `bootstrap.read_overview` antes de consultar CodeGraph (#18).
- **`/fg-plan --from <ruta-doc>`**: ingesta de doc externa (PRD, RFC) como contexto primario para el plan (#18).
- **`/fg-design` invoca `legacy-impact-analyzer`** ANTES de definir enfoque cuando `context.is_legacy: true` (#19).
- **Campos nuevos en `config.yaml.context`**: `last_detection`, `pending_detection`, `vision_skipped`, `is_legacy` (#16, #17, #19).

### Changed

- **`forge/cli.py`**: eliminado flag `--global`; agregados `--install-engram` y `--skip-engram-check`; `cmd_install` ahora es thin dispatch a `forge.installer.run`.
- **`forge/bootstrap.py`**: agregado `TODO(forge-bootstrap-package-root)` documentando el bug de `PACKAGE_ROOT` en instalaciones wheel non-editable (sin fix en este ciclo).
- **Rename de paths a español**: `docs/audit/changes/` → `docs/auditoria/cambios/`, `docs/audit/config.yaml` → `docs/auditoria/config.yaml`, `docs/architecture/` → `docs/arquitectura/`. Todas las skills, agentes, templates y `bootstrap.py` actualizados.
- **Split de template de diseño**: `templates/design-change.md` reemplazado por tres archivos con responsabilidad exclusiva: `templates/diseño.md` (estable), `templates/tareas.md` (mutable), `templates/decisiones.md` (append-only). Mapping canónico de sub-docs por agente documentado en `/fg-review`.
- **`print_report` del installer**: ya no menciona `/fg-setup` como próximo paso — refleja modelo latente (#15).
- **README "Después de instalar"**: reescrita — forge se invoca por intent natural, no por comando (#15).
- **README "Cómo se activa forge"** (sección nueva): tabla intent → cadena de skills disparada (#15).
- **Template `CLAUDE-md-institucional.md`**: reframeado a voz "el orquestador detecta intent"; nueva sección "Visión del sistema (modo bootstrap)" (#20).
- **Regla "nunca crear `docs/arquitectura/` vacío"**: relajada en `fg-setup.md` y `fg-update-arch.md` — modo bootstrap puede crearlos antes del primer código (#17).
- **Doctrina del modelo de delegación sincronizada con el código**: `templates/CLAUDE-md-institucional.md` y `README.md` ahora reflejan que `/fg-design` delega a `legacy-impact-analyzer` en proyectos legacy (comportamiento introducido en #19); la redacción previa afirmaba que solo `/fg-review` delegaba. Agregado un principio rector de delegación para evitar que la lista de skills delegadoras envejezca.

### Removed

- **Línea `print("  Próximo paso: /fg-setup")`** del `print_report` del installer (#15).
- **Flag `--global` del README**: ya removida del CLI en `6e4763b`, ahora también limpia en docs (#14).
- **Referencias stale a `commands/fg-*.md`** en README: la estructura de depósito no usa `commands/` (#14).

## [0.1.0] — 2026-05-27

### Added

- **6 skills** del workflow SDD: `/fg-setup`, `/fg-plan`, `/fg-design`, `/fg-implement`, `/fg-review`, `/fg-update-arch`.
- **6 sub-agentes** especialistas de review: `code-reviewer`, `security-reviewer`, `dba-reviewer`, `frontend-reviewer`, `qa-reviewer`, `legacy-impact-analyzer`. Solo `/fg-review` puede delegar a ellos.
- **Bootstrap por proyecto** (`forge/bootstrap.py`, invocado por `/fg-setup`): detecta stack, identifica test runner, activa Strict TDD si corresponde, mergea `CLAUDE.md` institucional, inicializa CodeGraph, configura `.gitignore`.
- **Detector de cambios estructurales** (`forge/structural_detector.py`, invocado por `/fg-review`): aplica 4 heurísticas en paralelo (manifiestos, módulos transversales, migraciones de BD, módulos top-level nuevos vía CodeGraph) y marca cambios como `structural: true` para disparar `/fg-update-arch`.
- **Configuración per-project** (en `<proyecto>/config/`): `modulos-transversales.yaml` (qué considera estructural el detector). Lleva un bloque didáctico al tope explicando qué hace, cómo se usa y cómo ajustarlo.
- **Privacidad de engram por disciplina del agente**: el `CLAUDE.md` institucional que `/fg-setup` mergea incluye la regla operativa "engram persiste señales del proceso, no datos del dominio". No hay scrubber automático — la barrera es la disciplina del agente reforzada por el system prompt.
- **Strict TDD Mode + Triangulación** heredados como módulo compartido (`skills/_shared/strict-tdd.md` y `strict-tdd-verify.md`): ciclo de 7 pasos por tarea, triangulación obligatoria, banned assertion patterns auditados por `/fg-review`.
- **Persona del orquestador** "mentor cordial con rigor profesional" con 10 reglas no negociables, en español.
- **Convención de cambios**: un cambio = una carpeta `docs/audit/changes/<YYYY-MM-tipo-nombre>/` con `README.md` (portada humano) + `design.md` (técnico vivo). Sin Envelope JSON estricto.
- **Idioma**: artefactos al dev en español; identificadores de código, conventional types y nombres de tools/MCPs/hooks en inglés.
- **Licencia MIT**.

### Notes

Esta es la primera versión publicada. El producto es **pre-estable** — pueden haber cambios incompatibles entre `0.x.y` y `0.x.z`. Usar en entornos productivos críticos solo después de validación local.

[Unreleased]: https://github.com/GomezFabricio/forge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/GomezFabricio/forge/releases/tag/v0.1.0
