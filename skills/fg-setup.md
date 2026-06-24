---
name: fg-setup
description: Instala forge en un proyecto existente. Idempotente. Detecta stack, genera docs/auditoria/config.yaml con defaults, inicializa CodeGraph, escribe el placeholder de skill-registry (el índice real lo genera /fg-update-registry). NO crea CLAUDE.md (la doctrina del orquestador es global, vía forge install). NO activa Strict TDD ni genera scaffolding del proyecto.
when_to_apply: Una vez al adoptar forge en un proyecto. Re-ejecutable para upgrade — detecta lo existente y solo agrega lo faltante.
---

> **ORCHESTRATOR GATE**: Si cargaste esta skill vía la tool `Skill`, sos el ORQUESTADOR — STOP.
> NO ejecutes estas instrucciones inline. Delegá al sub-agente `fg-setup` usando la primitiva
> de delegación de tu plataforma (ej. la tool `Task` o el sub-agente nativo). Esta skill es
> solo para EXECUTORS.

## Executor Override

Si SOS el sub-agente `fg-setup` (NO el orquestador), el gate de arriba NO aplica. Continuá con
el trabajo de la fase que sigue. NO delegues. NO llamés a la tool `Skill`. NO llamés a la tool
`Task`. Sos el executor — ejecutá.

> Cargar antes: `skills/_shared/fg-phase-common.md` (secciones A, B, E)

# /fg-setup

## Propósito

Adoptar forge en un proyecto existente: generar la estructura mínima de `docs/`, generar `docs/auditoria/config.yaml`, e indexar el código con CodeGraph. La doctrina del orquestador (persona, reglas) NO se configura acá: es global (`~/.claude/CLAUDE.md`, vía `forge install`).

**Lo que NO hace** (para evitar confusión con scaffolders tradicionales):

- No genera el scaffolding del proyecto (compose, Makefile, deploy/, src/, etc.) — eso es trabajo del análisis o del dev, no del producto.
- No pregunta por stack/perfil para imponer arquitectura.
- No genera `pyproject.toml` u otros manifiestos de dependencias.
- No crea `docs/arquitectura/` sin contenido real. En modo `bootstrap`, `overview.md` y `stack.md` se generan desde la conversación de visión (paso 10). `/fg-update-arch` reconcilia con código existente.

## Cuándo aplicarla

- Una vez al incorporar forge a un proyecto.
- Re-invocable para upgrade: detecta lo existente, mergea archivos sin sobrescribir, solo agrega lo faltante. Idempotente.

## Proceso

### 1. Detectar modo de operación

Llamar `bootstrap.detect_mode(root)` para determinar el modo antes de cualquier otra acción.

| Condición en `root` | Modo | Comportamiento de /fg-setup |
|---|---|---|
| `.forge/` existe | `upgrade` | Mergear incremental; re-detectar stack si `pending_detection: true` |
| `.git/` existe O hay manifiesto conocido | `adopt` | Comportamiento actual completo: detectar stack, crear config |
| Ninguna de las anteriores | `bootstrap` | Crear config con `pending_detection: true`, `stacks: []`; NO abortar |

**Modo bootstrap**: el directorio no tiene señales de un proyecto todavía. Está bien — forge puede inicializarse en un directorio vacío. En este modo:
- Saltear la detección de stack obligatoria.
- Crear `docs/auditoria/config.yaml` con `pending_detection: true` y `stacks: []`.
- Si `.git/` no existe, **NO preguntar inline** (un sub-agente no puede; ver `_shared/fg-phase-common.md` Sección B.1). Continuar el setup sin git, reportar `git_initialized: false`, y agregar al envelope:

  ```yaml
  decisions_needed:
    - question: "No encontré un repositorio git en el proyecto. ¿Querés que se corra `git init`?"
      options: [Sí, No]
      default: Sí
  ```

  El **orquestador** le pregunta al dev; si responde que sí, corre `git init` (o re-invoca el setup). La fase NO corre `git init` por su cuenta ni insiste.

  **El código Python (`bootstrap.run()`) NO corre `git init`** — solo reporta si `.git/` existe.

### 2. Detectar el stack del proyecto

Leer manifiestos para identificar lenguaje y framework principal. Esto se usa para:

- Configurar bien CodeGraph (qué parsers activar).
- Decidir qué test runner buscar.

**No se usa** para imponer arquitectura. Es información operativa, no opinión sobre cómo estructurar el código.

Heurísticas:

| Archivo detectado | Stack inferido |
|---|---|
| `pyproject.toml`, `requirements.txt`, `setup.py` | Python |
| `package.json` | Node (JS/TS según `tsconfig.json`) |
| `go.mod` | Go |
| `pom.xml`, `build.gradle` | Java |
| `Cargo.toml` | Rust |
| `composer.json` | PHP |

Si hay varios manifiestos, reportar todos al dev (proyecto polyglot).

### 3. Detectar testing capabilities (sin activar TDD)

Identificar el **test runner** del proyecto: `pytest` (Python), `vitest`/`jest` (Node), `go test` (Go), `mvn`/`gradle` (Java), `cargo test` (Rust), etc. Comando exacto para correr tests y manifiesto del que se infirió.

La detección **NO activa Strict TDD**. Es información que se vuelca al `docs/auditoria/config.yaml` (paso 5) para que el dev decida por proyecto si activar el ciclo TDD o no.

### 4. Crear estructura mínima de carpetas

```
docs/
└── auditoria/           ← cadena de auditoría IA-asistida
    └── cambios/         ← vacío, listo para recibir cambios
.atl/                    ← donde vive el skill-registry
.codegraph/              ← índice de CodeGraph (gitignored)
config/                  ← YAMLs por proyecto (modulos-transversales)
```

Si alguna carpeta ya existe, no la toca.

### 5. Generar `docs/auditoria/config.yaml`

Es la configuración persistente del proyecto que el equipo edita a mano para decidir cómo corre el workflow forge. Se genera con la detección del paso 3 y defaults conservadores.

Si `docs/auditoria/config.yaml` ya existe (re-ejecución de `/fg-setup`), **NO sobrescribir**. Solo se crea cuando no existe.

Junto con el config, `/fg-setup` deposita `docs/auditoria/guardrails.yaml` (la plantilla de reglas del hook de guardrails `PreToolUse`), con la misma semántica idempotente: se crea si no existe, se preserva si ya está.

Formato generado (con comentarios densos para que el equipo entienda cada key sin contexto adicional):

```yaml
schema: forge

context:
  stacks:                             # stacks detectados (python, node, etc.)
    - Python
  test_runner:                        # runner detectado al correr /fg-setup
    name: pytest
    command: pytest
    detected_from: pyproject.toml

rules:
  workflow:
    # cycle_mode: cómo corren las 4 fases del workflow forge.
    #   "interactive" = pausa entre fases para revisar. "automatic" = sin pausa.
    # el orquestador lo pregunta una vez por sesión (post-explore) y cachea la respuesta.
    cycle_mode: interactive

    # model_profile: qué modelos usa el orquestador por fase (equilibrado/performance/basico).
    # El orquestador lo PROPONE en el primer setup (ver "Decisiones para el orquestador");
    # default equilibrado (opus en plan/design/review, sonnet en executors).
    model_profile: equilibrado

  pr_size:
    # Controls del Review Workload Forecast — ver /fg-design y fg-phase-common.md Sección C.
    budget_lines: 400       # umbral de "PR grande" (líneas cambiadas)
    suggest_split: false    # si sugerir chained PRs al superar el budget
    enforcement: off        # off | warn | block (ver fg-phase-common.md Sección C)

  implement:
    # Si true, /fg-implement aplica Safety Net → RED → GREEN → TRIANGULATE → REFACTOR.
    tdd: false
    # Comando de test. Si vacío, usa context.test_runner.command.
    test_command: ""
    # Máximo de tareas por batch. /fg-implement corta al llegar al límite y reporta.
    max_tasks_per_batch: 20

  review:
    # Comando que /fg-review usa para validar la suite completa al cierre.
    test_command: ""
    # Cobertura mínima requerida sobre archivos cambiados (0 = sin enforcement).
    coverage_threshold: 0
```

Avisar al dev: "TDD está OFF por default. Para activarlo, editá `docs/auditoria/config.yaml` y cambiá `rules.implement.tdd` a `true`."

### 6. CLAUDE.md — NO tocar

`/fg-setup` **NO crea ni mergea** ningún `CLAUDE.md`. La doctrina del orquestador (persona, engram, mecánica TDD, ceremonia, workflow) es **global**: la instala `forge install` en `~/.claude/CLAUDE.md`. Si el proyecto tiene su propio `CLAUDE.md`, es del dev (reglas específicas del proyecto) — no lo toques.

### 7. Inicializar CodeGraph

- Verificar que el binario de CodeGraph esté disponible.
- Indexar el código actual del proyecto en `.codegraph/codegraph.db`.
- Reportar al dev la cantidad de nodos y aristas detectados.

### 8. Generar `.atl/skill-registry.md` (placeholder)

Llamar `bootstrap.generate_skill_registry_placeholder(root)` para crear el archivo `.atl/skill-registry.md` si no existe. Este paso solo escribe el placeholder; el registry real con el índice de skills se genera cuando el orquestador invoca `/fg-update-registry` después de completar el setup.

El orquestador DEBE invocar `/fg-update-registry` como siguiente paso después de que `/fg-setup` termine con éxito.

### 9. Actualizar `.gitignore`

- Agregar `.codegraph/` (ignorado completo).
- Agregar `.engram/` con excepción para `.engram/chunks/` (cross-machine memory).

Si el `.gitignore` ya tiene esas líneas, no duplicar.

### 10. Visión del sistema — la conduce el ORQUESTADOR (solo en modo bootstrap)

Si `mode != bootstrap` → saltar todo el paso 10 y continuar al paso 11. Envelope: `vision_status: n/a`.

La conversación de visión es **multi-turno**, así que **este executor NO la ejecuta** (un sub-agente no puede conversar con el dev; ver `_shared/fg-phase-common.md` Sección B.1). La conduce el orquestador (ver la doctrina en `~/.claude/CLAUDE.md`). Este paso solo decide si la visión hace falta y, en la re-invocación del orquestador, ESCRIBE los docs.

#### 10a. Idempotencia

Verificar antes de iniciar la conversación:

1. Si `docs/arquitectura/overview.md` ya existe → saltar el sub-flow, continuar al paso 11. Envelope: `vision_status: preserved`.
2. Si `config.yaml` tiene `context.vision_skipped: true` → NO reintentar por cuenta propia: devolver `decisions_needed` (`question: "La visión fue declinada antes. ¿Reintentarla?"`, `options: [Sí, No]`, `default: No`) y `vision_status: skipped`. El orquestador decide.

#### 10b. Si la visión hace falta y el orquestador NO mandó contenido aún

Devolver, **sin conversar**:
- `vision_status: pending-orchestrator`.
- En `decisions_needed`, la señal de que el orquestador debe conducir la conversación de visión. Las 5 preguntas guía que el orquestador usa:
  1. ¿Qué es este sistema? ¿Quién lo usa? ¿Qué problema resuelve?
  2. ¿Multi-tenant o single-tenant? Roles principales.
  3. ¿Web / mobile / CLI / API pura? ¿Estrategia de autenticación?
  4. Stack tecnológico.
  5. Módulos o áreas principales previstas.

El resto del setup (config, CodeGraph, etc.) ya se completó en los pasos anteriores — `pending-orchestrator` no bloquea esos artefactos.

#### 10c. Si el orquestador re-invoca con el contenido aceptado

Cuando el orquestador, tras conducir la conversación y obtener el OK del dev, re-invoca `/fg-setup` pasándole el `overview_content` y el `stack_content` aceptados:

- Llamar `bootstrap.create_arquitectura_docs(root, overview_content, stack_content)`.
- Si el dev mencionó stacks, llamar también `bootstrap.patch_config_stacks(root, stacks)` y loguear en el envelope: "stacks actualizados en config.yaml: [<stack(s)>]".
- Agregar paths al envelope (`files_created` / `files_preserved`). Envelope: `vision_status: completed`.

Si el orquestador informa que el dev declinó la visión: llamar `bootstrap.mark_vision_skipped(root)`. Envelope: `vision_status: skipped`. Warning: "Visión saltada — overview.md y stack.md no se generaron. Re-ejecutar /fg-setup o /fg-update-arch para crearlos."

**Regla de no-invención** (vigente para el orquestador al conversar y para el contenido que se escribe): incluir SOLO lo que el dev mencionó. NO inventar módulos, integraciones ni decisiones técnicas.

Si el contexto LLM se agota antes de completar el paso 10d → no escribir archivos parciales, no patchear config. Envelope: `vision_status: incomplete` con advertencia explicando la interrupción.

### 11. Reportar al dev

Imprimir en español:

```
forge inicializado en modo: {modo}
forge instalado en {nombre del proyecto}

Stack detectado: {stack o "ninguno (bootstrap — re-detecta cuando agregues manifiestos)"}
Test runner: {comando ({nombre}, detectado de {manifiesto}) | "no detectado"}
CodeGraph: {N nodos, N aristas indexados | "no inicializado"}

Archivos generados:
- docs/auditoria/config.yaml ({creado | preservado existente})
- docs/auditoria/guardrails.yaml ({creado | preservado existente})
- config/modulos-transversales.yaml ({creado | preservado existente})
- .atl/skill-registry.md (placeholder — el registry real lo genera /fg-update-registry)
- .gitignore (actualizado)

Nota: TDD está OFF por default. Para activarlo, editá docs/auditoria/config.yaml
      y cambiá rules.implement.tdd a true.

Próximo paso sugerido: /fg-update-registry (genera el índice de skills del proyecto)
```

## Reglas

### Siempre

- Idempotente: re-ejecutar no rompe nada, solo agrega lo faltante.
- Mergear archivos pre-existentes (gitignore, modulos-transversales.yaml) sin sobrescribir.
- Reportar al dev qué se hizo y qué se preservó.
- Generar `docs/auditoria/config.yaml` con la detección del paso 3 y defaults conservadores. NO sobrescribir si ya existe.
- NO activar Strict TDD desde `/fg-setup` — eso lo decide el dev editando el config a mano.

### Decisiones para el orquestador

Estos casos NO se preguntan inline (un sub-agente no puede; ver `_shared/fg-phase-common.md` Sección B.1). Devolverlos en `decisions_needed` para que el orquestador los resuelva con el dev:

- Si hay múltiples manifiestos (polyglot): `decisions_needed` con la pregunta de cuál es el principal para CodeGraph y las opciones detectadas. Mientras tanto, indexar con un default razonable y reportarlo.
- Si CodeGraph no está disponible: `decisions_needed` con opciones `[Seguir sin CodeGraph (degradado), Instalarlo primero]`. Default: seguir degradado.
- Perfil de modelo (`rules.workflow.model_profile`): `decisions_needed` proponiendo qué modelos usará el orquestador por fase. La fase deja escrito el default `equilibrado` en el `config.yaml`; si el dev elige otro, el orquestador actualiza la clave (no hace falta re-correr el setup). Pregunta sugerida:

  ```yaml
  decisions_needed:
    - question: "¿Qué perfil de modelo querés para este proyecto?"
      options: [equilibrado, performance, basico]
      default: equilibrado
      # equilibrado = opus en plan/design/review, sonnet en executors
      # performance = opus en todas las fases (máxima calidad, mayor costo)
      # basico      = sonnet en plan/design/review, haiku en executors (rápido/económico)
  ```

### Nunca

- Sobrescribir archivos existentes sin permiso.
- Generar scaffolding del proyecto (compose, Makefile, deploy/, src/, etc.).
- Preguntar por stack/perfil para imponer arquitectura.
- En modo bootstrap, `overview.md` y `stack.md` se crean a partir de la conversación de visión del sistema (paso 10). `/fg-update-arch` sigue siendo el mecanismo para reconciliar con código existente y agregar ADRs.
- Indexar CodeGraph en background sin avisar al dev (puede tardar en proyectos grandes).

## Envelope de retorno

```yaml
status: success | partial | blocked
executive_summary: 1-2 oraciones del setup completado
mode: bootstrap | adopt | upgrade        # modo detectado por detect_mode(root)
stack_detected: <stack> | null           # null en modo bootstrap (sin manifiestos)
test_runner: <comando> | null            # null en modo bootstrap
audit_config: created | preserved
pending_detection: true | false          # true = sin manifiestos todavía; false = detectado
vision_status: completed | preserved | skipped | incomplete | n/a
  # completed  = sub-flow corrió, overview.md + stack.md escritos
  # preserved  = overview.md ya existía, sub-flow saltado
  # skipped    = dev declinó (vision_skipped: true en config)
  # incomplete = sub-flow interrumpido por budget de contexto LLM
  # n/a        = mode != bootstrap
codegraph_indexed:
  nodes: <N>
  edges: <N>
files_created:
  - <lista de archivos nuevos>
files_merged:
  - <lista de archivos que se mergearon con contenido pre-existente>
files_preserved:
  - <lista de archivos que ya existían y no se tocaron>
warnings:
  - <ej: "no se detectó test runner — config.yaml queda con test_runner: null">
next_recommended: /fg-update-registry   # genera el skill registry real tras el setup
skill_resolution: paths-injected | fallback-registry | fallback-path | none
```
