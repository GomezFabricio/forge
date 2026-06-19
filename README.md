# forge

> Workflow de **Spec-Driven Development** para Claude Code, pensado para entornos críticos: privacidad rigurosa de datos sensibles, auditoría trazable de cada decisión asistida por IA, y permisos estrictos por defecto.

[![Versión](https://img.shields.io/badge/versión-0.1.0-blue.svg)](https://github.com/GomezFabricio/forge/releases)
[![Licencia](https://img.shields.io/badge/licencia-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

> **Estado**: `v0.1.0` — pre-estable. La API y el comportamiento pueden cambiar entre versiones menores. Usar en producción crítica solo después de validación local.

---

## Qué es forge

**forge** es una herramienta que se instala como skills, hooks y sub-agentes dentro de Claude Code, y aporta un workflow estructurado de SDD pensado para equipos que trabajan en entornos sensibles (sector público, salud, finanzas, sistemas legacy con compliance estricto).

Los tres ejes que el producto endurece sobre la operación habitual de Claude Code:

1. **Privacidad** — la regla operativa "engram persiste señales del proceso, no datos del dominio" está incorporada al `CLAUDE.md` institucional que `forge install` instala globalmente en `~/.claude/`. La disciplina del agente es la barrera principal contra que identificadores y secretos del dominio terminen en memoria persistente.
2. **Auditoría** — cada cambio queda registrado en `docs/auditoria/cambios/<cambio>/` con un `README.md` (portada humano), `diseño.md` (técnico estable), `tareas.md` (checklist) y `decisiones.md` (decisiones técnicas). El historial de git es la cadena de auditoría.
3. **Permisos estrictos** — el agente no ejecuta acciones destructivas sin autorización explícita. Configuración `bypassPermissions: false` por defecto.

forge **no reemplaza** Claude Code — vive encima de él, agregando las skills, hooks y sub-agentes que el workflow necesita.

Para una guía completa de uso por escenario, configuración y troubleshooting: [docs/guia-de-uso.md](docs/guia-de-uso.md).

---

## Instalación

forge corre sobre **Claude Code** en Windows, macOS y Linux. La instalación es **una sola vez por máquina**: deposita skills, sub-agentes y el hook PII en `~/.claude/` y queda latente en todos tus proyectos.

### Compatibilidad

| Sistema operativo | Arquitectura | Estado |
|---|---|---|
| Windows 10 / 11 | x64, arm64 | Soportado — plataforma de desarrollo principal |
| macOS 12+ | Apple Silicon (arm64), Intel (x64) | Soportado por diseño |
| Linux (glibc) | x64, arm64 | Soportado por diseño |

> **Sobre la validación, sin maquillaje**: el código tiene rutas explícitas para las tres plataformas (descarga de engram y CodeGraph por OS + arquitectura, scripts `.sh` y `.ps1`). La suite (~542 tests) corre con subprocess y red mockeados y se ejercita principalmente en Windows; **todavía no hay CI multi-OS**. En macOS/Linux puede haber detalles del entorno por pulir.

### Prerequisitos

| Requisito | Por qué | Cómo verificar |
|---|---|---|
| **Python 3.10+** | El paquete y los hooks corren en Python. | `python --version` o `python3 --version` |
| **Claude Code** | Es el runtime donde viven las skills y sub-agentes. | `claude --version` |
| **git** | Para instalar desde el repositorio. | `git --version` |
| **pipx** | Aísla forge del Python del sistema. El instalador lo instala si falta. | `pipx --version` |
| **CodeGraph** *(opcional, recomendado)* | Análisis estructural 100% local del código. El instalador ofrece instalarlo. | — |

### Paso a paso

Elegí **una** de las dos vías. Las dos terminan con forge instalado en `~/.claude/` y listo para usar.

#### Opción A — vía rápida (un comando)

Los scripts verifican Python 3.10+, aseguran `pipx`, instalan forge en un entorno aislado y corren `forge install`. Cualquier argumento extra se pasa tal cual a `forge install` (ej. `--skip-context7`).

**Linux / Mac**:

```bash
curl -sSL https://github.com/GomezFabricio/forge/raw/main/install.sh | bash
```

**Windows (PowerShell)**:

```powershell
iwr https://github.com/GomezFabricio/forge/raw/main/install.ps1 -useb | iex
```

> **Nota de compliance**: el `curl … | bash` ejecuta un script remoto. Si tu política exige auditarlo antes, descargalo, revisalo y corré la Opción B.

#### Opción B — vía institucional (clon + pipx, auditable)

Para equipos con políticas que no permiten ejecutar scripts remotos sin auditoría previa:

```bash
git clone https://github.com/GomezFabricio/forge
cd forge
pipx install --editable . --include-deps
forge install
```

Esto instala el paquete en modo editable con pipx y ejecuta `forge install` directamente, que deposita las skills, agents y MCP en `~/.claude/`.

#### Verificar la instalación

```bash
forge --version          # imprime la versión instalada
```

Después abrí Claude Code en cualquier proyecto y describí lo que querés hacer en lenguaje natural — forge se activa solo según el contexto (ver [Cómo se activa forge](#cómo-se-activa-forge)).

### Qué hace el instalador

La instalación ejecuta los siguientes pasos en cadena:

1. Verifica que haya **Python 3.10+** disponible. Si no encuentra `pipx`, lo instala (`python -m pip install --user pipx` + `pipx ensurepath`).
2. Instala el paquete con **pipx** desde el repositorio (`pipx install --force git+https://github.com/GomezFabricio/forge.git`; la vía institucional usa `--editable .` sobre el clon local). forge **no está publicado en PyPI** todavía. pipx lo aísla del Python global del sistema y permite upgrade/uninstall limpios.
3. Ejecuta **`forge install`**, que deposita en `~/.claude/`:
   - `skills/<stem>/SKILL.md` — las 8 skills del workflow (`fg-setup`, `fg-explore`, `fg-plan`, `fg-design`, `fg-implement`, `fg-review`, `fg-update-arch`, `fg-update-registry`), cada una en su propia carpeta.
   - `skills/forge-shared/<name>/SKILL.md` — referencias compartidas (`skill-resolver`, `engram-protocol`, `fg-phase-common`), con frontmatter que evita invocación accidental por el modelo.
   - `skills/fg-implement/strict-tdd.md` y `skills/fg-review/strict-tdd-verify.md` — módulos del ciclo Strict TDD, co-locados con su skill consumidora.
   - `agents/<name>.md` — los 14 agentes (copia flat): 6 reviewers especialistas (`code-reviewer`, `security-reviewer`, `dba-reviewer`, `frontend-reviewer`, `qa-reviewer`, `legacy-impact-analyzer`) + 8 executors `fg-*` (la capa agents del modelo de 3 capas, uno por fase).
   - `commands/fg-*.md` — los 8 entrypoints de slash command (capa commands del modelo de 3 capas).
   - (entrada en `~/.claude.json` `mcpServers.engram`) — registro MCP de engram en el archivo global de Claude Code (solo si engram se instala durante `forge install`).
   - `settings.json` — registra el hook PII `UserPromptSubmit` y el hook de guardrails `PreToolUse` (merge idempotente, preservando hooks existentes). Omitibles con `--skip-pii-hook` y `--skip-guard-hook` respectivamente.
   - `CLAUDE.md` — la **doctrina global del orquestador** (el institucional). Reemplaza el `~/.claude/CLAUDE.md` actual respaldando el previo en `~/.claude/backup/forge/<fecha>/` si difiere; si ya es el de forge, no hace nada (idempotente).

> **v0.1.0**: `forge install` está implementado end-to-end. Deposita skills, sub-agentes y commands en `~/.claude/`, instala la doctrina global del orquestador en `~/.claude/CLAUDE.md` (con backup del previo), y registra opcionalmente los MCP de engram/CodeGraph/Context7 y los hooks PII y guardrails en `~/.claude/settings.json`.

### Después de instalar

Una vez instalado, forge se invoca solo según el contexto de cada conversación. Hablá normal con Claude — si la tarea encaja con el workflow, el orquestador inicializa forge y guía la sesión. No necesitás conocer los slash commands; existen para casos avanzados (scripts, automatización).

---

## Cómo se activa forge

Forge no se "activa" ni se "desactiva" — está latente desde que lo instalaste globalmente. El orquestador detecta tu intención conversacional y arranca el flujo correspondiente sin pedirte permiso.

| Cuando le decís a Claude… | Forge hace |
|---|---|
| "quiero hacer un sistema de X" | Inicializa el proyecto si hace falta, charla con vos para entender el sistema, arma `docs/arquitectura/overview.md`, y te guía feature por feature. |
| "implementá esto según docs/prd.md" | Lee el documento, valida consistencia, surface gaps, y te guía slice por slice. |
| "agregame [feature] al sistema" | Adopta forge en el proyecto, analiza el código con CodeGraph, y planifica el cambio minimizando impacto. |
| "necesito refactorizar este legacy" | Adopta + analiza dependencias ocultas + propone estrategia de migración (strangler fig, branch by abstraction, etc.) antes de tocar nada. |

### Cuándo NO invocar forge

El orquestador NO mete forge cuando:

- El cambio es un fix de typo, una línea, o un ajuste de comentario.
- Estás explorando o haciendo preguntas sin modificar código.
- Decís explícitamente "sin forge" o "edición libre".

No tenés que memorizar slash commands. Si querés invocar una skill manualmente para casos avanzados (scripts, automatización), los comandos `/fg-*` siguen disponibles.

---

## Workflow

Un cambio en forge sigue 4 fases por defecto, con una fase 0 opcional de exploración y una skill de mantenimiento de arquitectura:

```
Setup del proyecto (una vez):  /fg-setup
Exploración (fase 0 opcional): /fg-explore
Por cada cambio:               /fg-plan → /fg-design → /fg-implement → /fg-review
Mantenimiento arquitectura:    /fg-update-arch      (sugerida por /fg-review)
Mantenimiento del registry:    /fg-update-registry  (tras instalar/crear/renombrar skills)
```

### Gradación de ceremonia

El orquestador evalúa cada cambio antes de arrancar y propone el nivel de ritual mínimo adecuado aplicando las reglas de gradación que forge instala en el CLAUDE.md institucional. El dev confirma o ajusta; forge nunca impone el nivel sin consentimiento.

| Nivel | Qué saltea | Piso innegociable |
|---|---|---|
| **Libre** | Todo el ciclo — forge no interviene | — |
| **Rápido** | Solo `/fg-design`; tareas se generan desde `templates/tareas-lite.md` | `/fg-review` siempre corre |
| **Completo** | Nada — ritual completo sin cambios | `/fg-review` siempre corre |

**Condición para modo Rápido**: la arquitectura debe estar al día. El orquestador lo verifica mediante Grep sobre los READMEs de cambios. Si hay cambios estructurales sin sincronizar, el orquestador eleva automáticamente a Completo.

### Las 8 skills

| Skill | Propósito |
|---|---|
| `/fg-setup` | Adopta forge en el proyecto. Idempotente, re-invocable para upgrade. |
| `/fg-explore [área]` | Fase 0 opcional. Produce el mapa del cambio vía CodeGraph (`exploracion.md`): archivos afectados reales, consumidores, acoplamientos no obvios. Reutilizable por `/fg-design`. Puede correr antes de `/fg-plan`. |
| `/fg-plan <descripción libre>` | Crea la carpeta `docs/auditoria/cambios/<YYYY-MM-tipo-nombre>/` con el `README.md` inicial. Infiere `tipo` (feat/fix/refactor/...) y `nombre` desde el lenguaje natural. El nivel de ceremonia ya fue determinado por el orquestador antes de invocar esta skill. |
| `/fg-design` | Crea `diseño.md` (enfoque + arquitectura + archivos afectados), `tareas.md` (checklist) y `decisiones.md` (decisiones técnicas iniciales), todos vía CodeGraph. |
| `/fg-implement` | Implementa el checklist tarea por tarea aplicando el ciclo Strict TDD si está activo (Safety Net → Understand → RED → GREEN → TRIANGULATE → REFACTOR). |
| `/fg-review` | Corre la suite completa, valida TDD Cycle Evidence, audita assertion quality, delega a sub-agentes especialistas según el cambio, y consolida el cierre. Única skill que delega. |
| `/fg-update-arch` | Reconcilia la documentación permanente del proyecto (`docs/arquitectura/`) con la realidad del código. Propone diff por archivo, nunca todo-o-nada. |
| `/fg-update-registry` | Genera o regenera el índice de skills del proyecto en `.atl/skill-registry.md`. Invocar después de `/fg-setup` y al instalar, crear, mover o renombrar skills. |

### Estructura de docs por cambio

```
docs/
├── arquitectura/                ← documentación permanente (gestionada por /fg-update-arch)
│   ├── overview.md
│   ├── stack.md
│   └── decisions/               ← ADRs
└── auditoria/                   ← cadena de auditoría IA-asistida
    └── cambios/
        └── 2026-05-feat-login/  ← un cambio
            ├── README.md        ← portada (lectura humano)
            ├── diseño.md        ← técnico estable (solo escribe /fg-design)
            ├── tareas.md        ← checklist mutable (/fg-implement tacha)
            ├── decisiones.md    ← decisiones técnicas (append-only)
            ├── evidencia-tdd.md ← evidencia del ciclo TDD (/fg-implement; solo si TDD activo)
            └── assets/          ← opcional
```

---

## Sub-agentes especialistas

`/fg-review` delega a sub-agentes de review según el contexto del cambio; además, `/fg-design` invoca al `legacy-impact-analyzer` antes de implementar en proyectos legacy. Cada uno aporta una mirada especializada al envelope final:

| Sub-agente | Cuándo se invoca |
|---|---|
| `code-reviewer` | Siempre. Review general estilo Senior Staff Engineer. |
| `security-reviewer` | Cuando el cambio toca auth, datos sensibles o endpoints públicos. |
| `dba-reviewer` | Cuando hay migraciones o queries pesadas. |
| `frontend-reviewer` | Cuando toca UI/UX (componentes, páginas). |
| `qa-reviewer` | Cuando hay tests complejos o de integración nuevos. |
| `legacy-impact-analyzer` | Cuando el proyecto está marcado como legacy. Invocado por `/fg-design` (impacto pre-implementación) y por `/fg-review`. Mapea acoplamientos ocultos con CodeGraph. |

Las demás skills (`/fg-setup`, `/fg-plan`, `/fg-implement`, `/fg-update-arch`) son **ejecutores estrictos** — no delegan.

---

## Defensa en profundidad

forge aplica cuatro capas de control complementarias:

| Capa | Mecanismo | Kill-switch |
|---|---|---|
| **Hooks de entrada** | `UserPromptSubmit` redacta PII antes de que el prompt llegue a Anthropic. Fail-open. | `FORGE_PII_DISABLE=1` |
| **Guardrails de ejecución** | `PreToolUse` evalúa reglas `block`/`confirm` en `docs/auditoria/guardrails.yaml` antes de cada Bash command. Fail-open y best-effort: un patrón con backtracking catastrófico escrito por el usuario es responsabilidad del usuario (el guard acota la longitud del input pero no garantiza terminación en patrones patológicos). | `FORGE_GUARD_DISABLE=1` |
| **Review con juicio** | `/fg-review` OBLIGATORIO en todo ciclo. Hasta 6 reviewers especialistas + auditoría de assertions + TDD compliance. | No tiene (piso innegociable) |
| **Contratos en CI del repo forge** | Tests de consistencia determinísticos: paridad agents↔skills, enums desde fuente única, anti-regresiones en templates. Protegen el repo de forge, no los proyectos del dev. | No aplica |

Para detalles de configuración y límites de cada capa: [docs/guia-de-uso.md §8](docs/guia-de-uso.md#8-defensa-en-profundidad).

---

## Configuración por proyecto

Después de correr `/fg-setup`, el proyecto tiene dos archivos editables:

### `docs/auditoria/config.yaml`

Controla el comportamiento del workflow forge para el proyecto. `/fg-setup` lo genera con defaults conservadores y comentarios densos — legible sin contexto adicional. El equipo lo edita a mano y lo commitea.

Los bloques más importantes:

#### `rules.pr_size` — Review Workload Forecast

`/fg-design` estima cuántas líneas tendrá el PR al cerrar. El bloque `rules.pr_size` controla qué hace con esa estimación:

| Modo (`enforcement`) | Comportamiento |
|---|---|
| `off` | Sin mención del budget. 1 issue = 1 MR sin fricción. **Default recomendado** para la mayoría de los equipos. |
| `warn` | Avisa cuando el PR supera `budget_lines` pero **no bloquea**. Útil para devs y freelancers que quieren visibilidad sin fricción. |
| `block` | Exige documentar `size:exception` en el PR body antes de continuar si el PR supera el budget. Para equipos con presión real sobre calidad de review. |

```yaml
rules:
  pr_size:
    budget_lines: 400       # umbral de "PR grande" (heurística estándar: 400 líneas)
    suggest_split: false    # ¿sugerir partir en chained PRs cuando supera el budget?
    enforcement: off        # off | warn | block
```

**forge nunca crea ramas ni PRs automáticamente** — el forecast es información, no acción. El dev siempre opt-in explícitamente a cualquier split.

#### `rules.implement.max_tasks_per_batch` — Batching de implementación

Si `/fg-design` genera más tareas que este límite, `/fg-implement` implementa hasta el límite, guarda el progreso en engram, y le avisa al dev cuántas tareas quedan. La próxima invocación retoma donde quedó.

```yaml
rules:
  implement:
    max_tasks_per_batch: 20   # ajustar según el tamaño típico de los cambios del equipo
```

La norma sana es **"1 sesión = 1 ciclo"** — si un cambio requiere múltiples batches, correr cada uno en una sesión nueva para mantener el contexto del modelo fresco.

#### `rules.workflow.cycle_mode` — Default del modo de ciclo

Define el modo de ejecución sugerido para los ciclos del proyecto (`interactive` o `automatic`). El **orquestador** lo lee al comenzar el primer ciclo SDD de la sesión y lo usa como valor pre-seleccionado al preguntar — el dev siempre puede cambiar la elección por sesión.

#### `rules.workflow.ceremonial_threshold` — Sesgo del orquestador

Controla el nivel de ceremonia que el orquestador propone por defecto para el proyecto (señal de mayor precedencia en la gradación de ceremonia).

| Valor | Comportamiento |
|---|---|
| `auto` | El orquestador infiere el nivel por tipo de cambio y señales contextuales. **Default**. |
| `lite` | Sesga hacia Rápido para tipos ligeros (`docs`, `chore`, `test`, `style`) cuando la arquitectura está al día. Tipos no triviales (`feat`, `refactor`) siguen yendo a Completo. |
| `full` | Fuerza Completo en todos los cambios sin preguntar. Útil en proyectos críticos o bajo auditoría estricta. |

```yaml
rules:
  workflow:
    ceremonial_threshold: auto   # auto | lite | full
```

### `config/modulos-transversales.yaml`

Le indica al detector de cambios estructurales qué paths del proyecto son **transversales** — es decir, su modificación impacta varias áreas y debe disparar `/fg-update-arch`.

Ejemplos comentados típicos: `src/auth/`, `src/db/`, `src/logging/`, `src/middleware/`, `src/i18n/`. Descomentar los que apliquen a tu proyecto.

---

## Strict TDD Mode

forge soporta un ciclo Strict TDD opt-in. Está OFF por default — `/fg-setup` no lo activa, lo decide el equipo editando el archivo de configuración del proyecto.

**Activarlo**: editar `docs/auditoria/config.yaml` y cambiar `rules.implement.tdd` a `true`. El cambio queda versionado.

Cuando está activo:

- `/fg-implement` aplica el ciclo de 7 pasos por tarea: **Safety Net → Understand → RED → GREEN → TRIANGULATE → REFACTOR → Complete**.
- Las tres leyes se respetan: (1) no escribir producción sin test fallando, (2) no escribir más test que el necesario para fallar, (3) no escribir más código que el necesario para pasar.
- `/fg-review` audita assertion quality (tautologías, ghost loops, smoke tests, mock-heavy tests son flaggeados como WARNING o CRITICAL según severidad) y opcionalmente valida cobertura mínima (`rules.review.coverage_threshold`).

Cuando está OFF, `/fg-implement` opera en modo estándar y `/fg-review` aplica validación básica.

### Modo del ciclo SDD (interactivo / automático)

Independiente del TDD, el **modo de ejecución del ciclo** lo decide el dev al arrancar el primer ciclo de la sesión:

- **Interactivo**: cada fase pausa al cerrar y espera confirmación del dev para seguir.
- **Automático**: las fases se encadenan sin pausa hasta el final del ciclo.

La elección se cachea para la sesión actual — el **orquestador** pregunta una sola vez al comenzar el primer ciclo SDD de la sesión y reusa la respuesta para los ciclos siguientes. Sesión nueva → vuelve a preguntar. El cache no se persiste en filesystem.

---

## CodeGraph

forge integra [CodeGraph](https://github.com/colbymchenry/codegraph) (MIT, 100% local, 19 lenguajes) como herramienta oficial de análisis estructural del código. `/fg-setup` lo inicializa por proyecto.

CodeGraph se usa para:

- `/fg-plan` → identificar contexto del cambio sin grep ciego.
- `/fg-design` → llenar la sección "Archivos afectados" de `diseño.md`.
- `/fg-review` → detectar módulos top-level nuevos y cambios en dependencias.
- `/fg-update-arch` → reconciliar topología del código con la documentación.

Si CodeGraph no está disponible, forge sigue funcionando degradado (los detectores caen a heurísticas de paths).

---

## Context7 MCP

forge integra [Context7](https://context7.com) como herramienta opcional para obtener documentación actualizada de librerías externas durante la exploración e implementación.

### Cuándo se consulta

La consulta es **selectiva** para preservar el cupo de 1000 req/mes del pool gratuito:

- **TRIGGER A** — en `/fg-explore`: cuando el mapa detecta una librería externa en los archivos afectados y el cambio es de nivel `rapido` o `completo` (nunca en `libre`).
- **TRIGGER B** — en `/fg-implement`: cuando hay ambigüedad explícita sobre la API de una librería externa (firma, parámetros, comportamiento).

En cambios triviales (renombrados, typos, ajustes de estilo) Context7 **nunca** se consulta.

### Instalación

`forge install` registra el bloque MCP de Context7 en `~/.claude.json` automáticamente (vía `npx`, sin instalar ningún binario):

```bash
# Sin API key: usa pool anónimo (1000 req/mes compartido)
forge install

# Con API key personal: definir la variable de entorno ANTES de correr forge install
export CONTEXT7_API_KEY="tu-key-personal"
forge install

# Saltar Context7 si no lo querés
forge install --skip-context7
```

La key **nunca** se commitea ni se escribe en ningún archivo del repo. Solo se inyecta en `~/.claude.json` del dev (fuera del control de versiones).

### Privacidad

Context7 es un servicio externo (backend closed-source de Upstash). Qué datos viajan a Context7:

| Dato enviado | Ejemplo |
|-------------|---------|
| Nombre de la librería | `"react-query"` |
| Query de documentación | `"useQuery options"` |

Qué datos **nunca** salen del entorno local:

- Código fuente del proyecto.
- Rutas de archivos del repo.
- Nombres de variables, funciones o clases del codebase.
- Cualquier identificador del proyecto.

---

## Idioma

forge habla **español al dev**: mensajes, reportes, comentarios de los YAMLs, secciones del `CLAUDE.md` institucional, todos los artefactos generados.

Los **identificadores técnicos** (nombres de comandos, slash commands, hooks, tipos, conventional types como `feat`/`fix`/`refactor`) quedan en **inglés** porque son estándar transversal del ecosistema.

---

## Estructura del repo (source)

> Esta es la estructura del repo `forge` (source). **`forge install` distribuye estos archivos a `~/.claude/`** — el dev que adopta forge no necesita tener `skills/`, `agents/` ni `templates/` en su proyecto. La estructura del proyecto del dev tras `/fg-setup` se muestra más abajo.

```
forge/
├── forge/                       ← paquete Python instalable
│   ├── __init__.py
│   ├── cli.py                   ← entry point del binario `forge`
│   ├── bootstrap.py             ← ejecutor de /fg-setup (instala forge en un proyecto)
│   ├── installer.py             ← lógica de `forge install` (deposita skills, agents, MCP)
│   ├── structural_detector.py   ← detector de cambios estructurales usado por /fg-review
│   ├── filters/                 ← capa de filtrado PII (hook UserPromptSubmit)
│       ├── __init__.py
│       ├── analyzer.py          ← orquesta los recognizers y produce detecciones
│       ├── anonymizer.py        ← reemplaza entidades detectadas con placeholders
│       ├── hook_user_prompt.py  ← punto de entrada del hook UserPromptSubmit
│       ├── redaction_log.py     ← registro append-only de eventos de redacción
│       └── recognizers/         ← recognizers por tipo de entidad
│           ├── __init__.py
│           ├── ar_cbu.py        ← CBU argentino
│           ├── ar_cuit.py       ← CUIT/CUIL con dígito verificador AFIP
│           ├── ar_dni.py        ← DNI argentino
│           └── secrets.py       ← secretos técnicos (JWT, AWS keys, GitHub PAT, etc.)
│   └── guards/                  ← capa de guardrails (hook PreToolUse)
│       └── hook_pre_tool.py     ← punto de entrada del hook PreToolUse
├── skills/                      ← 8 skills + módulos compartidos (van a ~/.claude/skills/<stem>/SKILL.md y ~/.claude/skills/forge-shared/)
│   ├── fg-setup.md
│   ├── fg-explore.md
│   ├── fg-plan.md
│   ├── fg-design.md
│   ├── fg-implement.md
│   ├── fg-review.md
│   ├── fg-update-arch.md
│   ├── fg-update-registry.md
│   └── _shared/                 ← skill-resolver, persistence-contract, strict-tdd
├── agents/                      ← 14 agentes (van a ~/.claude/agents/): 6 reviewers + 8 executors fg-*
│   ├── code-reviewer.md         ← reviewers especialistas (invocados por /fg-review)
│   ├── security-reviewer.md
│   ├── dba-reviewer.md
│   ├── frontend-reviewer.md
│   ├── qa-reviewer.md
│   ├── legacy-impact-analyzer.md
│   ├── fg-setup.md              ← executors de fase (capa agents del modelo 3 capas)
│   ├── fg-explore.md
│   ├── fg-plan.md
│   ├── fg-design.md
│   ├── fg-implement.md
│   ├── fg-review.md
│   ├── fg-update-arch.md
│   └── fg-update-registry.md
├── config/                      ← template de configuración per-project (se copia al proyecto)
│   └── modulos-transversales.yaml
├── templates/                   ← templates de artefactos generados (se aplican al proyecto)
│   ├── README-change.md
│   ├── diseño.md
│   ├── tareas.md
│   ├── tareas-lite.md           ← template reducido para modo Rápido
│   ├── decisiones.md
│   ├── guardrails.yaml          ← plantilla de guardrails (depositada por /fg-setup)
│   └── CLAUDE-md-institucional.md
├── docs/                        ← documentación interna del paquete
│   └── codegraph-integration.md
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
└── .gitignore
```

## Estructura del proyecto del dev después de `/fg-setup`

Después de correr `/fg-setup` en un proyecto, forge crea **solo** lo siguiente. La doctrina del orquestador NO va acá: es global (`~/.claude/CLAUDE.md`, vía `forge install`). Las skills, agents y templates **no se copian** al proyecto — viven globalmente en `~/.claude/` y se descubren desde ahí.

```
mi-proyecto/
├── CLAUDE.md                    ← OPCIONAL, del dev (reglas específicas del proyecto). forge no lo crea.
├── config/
│   └── modulos-transversales.yaml   ← qué considera estructural el detector
├── docs/
│   └── auditoria/               ← cadena de auditoría IA-asistida
│       ├── index.md
│       └── cambios/             ← un cambio = una carpeta
│           └── 2026-05-feat-login/
│               ├── README.md        ← portada (lectura humano)
│               ├── diseño.md        ← técnico estable
│               ├── tareas.md        ← checklist mutable
│               ├── decisiones.md    ← decisiones técnicas
│               └── evidencia-tdd.md ← evidencia del ciclo TDD (solo si TDD activo)
├── .atl/
│   └── skill-registry.md        ← registry de skills resueltas para este proyecto
├── .codegraph/                  ← índice de CodeGraph (gitignored)
├── .engram/                     ← memoria persistente cross-session (gitignored salvo chunks/)
├── .forge/                      ← runtime de forge (gitignored)
└── .gitignore                   ← actualizado con las entradas necesarias
```

El resto del proyecto (`src/`, tests, build configs, etc.) lo administra el dev — forge no impone arquitectura.

---

## Contribuir

forge está en pre-estable (`0.x`). Las contribuciones son bienvenidas pero la superficie del producto puede cambiar entre versiones menores hasta llegar a `v1.0.0`.

Para reportar bugs o proponer mejoras: [issues del repo](https://github.com/GomezFabricio/forge/issues).

Para contribuir código:

1. Fork del repo.
2. `pipx install --editable . --include-deps` para desarrollo local.
3. `pytest` debe pasar.
4. `ruff check forge/` debe pasar limpio.
5. Pull request con descripción clara del cambio.

---

## PII filter

forge incluye un hook `UserPromptSubmit` que detecta y redacta datos personales e identificadores sensibles **antes** de que el prompt llegue a la API de Anthropic. El filtro opera en modo pattern-only (sin spaCy, sin modelos NLP), con cold start < 300ms en Windows.

### Qué detecta

22 tipos de entidad: identificadores argentinos (CUIT, DNI_AR, CBU), secretos técnicos (JWT, AWS_ACCESS_KEY, AWS_SECRET_KEY, GITHUB_PAT, GITHUB_FINE_GRAINED, OPENAI_KEY, ANTHROPIC_KEY, SLACK_TOKEN, STRIPE_KEY, PRIVATE_KEY_BLOCK, CONNECTION_STRING_PASSWORD, BEARER_TOKEN), y tipos Presidio built-in (CREDIT_CARD, EMAIL_ADDRESS, IBAN_CODE, IP_ADDRESS, PHONE_NUMBER, URL, CRYPTO).

### Cómo funciona

Cada detección reemplaza el dato con un placeholder estable: `[CUIT]`, `[JWT]`, `[AWS_ACCESS_KEY]`, etc. El prompt modificado llega a Claude en lugar del original. El texto circundante se preserva verbatim.

### Registro de auditoría

Cada redacción y cada passthrough se registran en `.forge/auditoria-pii.jsonl` (append-only, una línea JSON por evento). El log nunca contiene el texto del prompt — solo un hash SHA-256 truncado a 16 caracteres para correlación.

### Override: `#fg-pass`

Para pasar un prompt sin filtrar (fixtures, tests, datos de ejemplo documentados), incluir el marcador `#fg-pass` en cualquier parte del prompt:

```
CUIT del proveedor: 20-12345678-6  #fg-pass
```

El marcador es case-sensitive. `#FG-PASS`, `#fg_pass` o `# fg-pass` **no** activan el override.

### Registro del hook

`forge install` registra el hook automáticamente en `~/.claude/settings.json` (merge idempotente que preserva tus hooks existentes). El comando se ancla al intérprete donde quedó instalado forge (`sys.executable`), no a un `python` genérico del PATH — así funciona aunque forge viva en un venv aislado de pipx.

Si lo omitiste con `--skip-pii-hook`, o querés registrarlo a mano, agregá este bloque a `~/.claude/settings.json` (reemplazando el comando por la ruta de tu intérprete con forge instalado):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python -m forge.filters.hook_user_prompt"
          }
        ]
      }
    ]
  }
}
```

> En el bloque manual, `python` solo funciona si el intérprete del PATH tiene forge instalado. Con pipx (venv aislado) usá la ruta absoluta del intérprete del venv, ej. `~/.local/pipx/venvs/forge/bin/python -m forge.filters.hook_user_prompt`. El auto-registro de `forge install` ya resuelve esto solo.

### Kill-switch

Para desactivar el filtro sin revertir código:

```bash
export FORGE_PII_DISABLE=1
```

### Límites conocidos del filtro PII

**Comportamiento ante fallos del filtro (fail-open, ADR-4)**

Si el filtro falla durante la ejecución del hook (por ejemplo, crash de Presidio, error de importación, excepción no capturada), el prompt pasa a Anthropic **sin redactar**. Este comportamiento es intencional: la prioridad es no romper el loop de desarrollo bajo ninguna circunstancia. La compensación es el log de auditoría (`.forge/auditoria-pii.jsonl`), que registra todos los eventos incluyendo los de tipo `error`.

`FORGE_PII_DISABLE=1` desactiva el filtro deliberadamente — es un kill-switch distinto al fail-open. En entornos críticos, la mitigación disponible es revisar el log de auditoría para identificar prompts que no pasaron por el filtro.

**Redacción de cadenas de conexión (`CONNECTION_STRING_PASSWORD`)**

El detector de cadenas de conexión redacta el segmento completo `protocolo://usuario:contraseña@` y lo reemplaza por `[CONNECTION_STRING_PASSWORD]`. No es posible redactar solo la contraseña y preservar protocolo/usuario/host: Presidio no soporta reemplazo parcial dentro de un match. La sobre-redacción es segura por diseño — el riesgo es perder contexto de protocolo/host en el prompt, no exponer datos.

**Rotación del log de auditoría**

`.forge/auditoria-pii.jsonl` es append-only sin rotación automática. Cada entrada ocupa entre 150 y 200 bytes y solo se escribe cuando hay un evento de redacción, passthrough (`#fg-pass` o kill-switch) o error (no en cada prompt). En la práctica el archivo crece varios megabytes por año, no gigabytes. El dev es responsable del archivado y limpieza manual. El log **nunca contiene el texto del prompt** — solo un hash SHA-256 truncado a 16 caracteres hexadecimales para correlación.

---

## Licencia

[MIT](LICENSE). Copyright (c) 2026 Fabricio Gomez.
