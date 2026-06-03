---
name: fg-setup
description: Instala forge en un proyecto existente. Idempotente. Detecta stack, genera docs/auditoria/config.yaml con defaults, inicializa CodeGraph, genera CLAUDE.md institucional y skill-registry. NO activa Strict TDD ni genera scaffolding del proyecto.
when_to_apply: Una vez al adoptar forge en un proyecto. Re-ejecutable para upgrade — detecta lo existente y solo agrega lo faltante.
---

> Cargar antes: `skills/_shared/fg-phase-common.md` (secciones A, B, E)

# /fg-setup

## Propósito

Adoptar forge en un proyecto existente: instalar el harness de Claude Code (skills, sub-agentes), generar la estructura mínima de `docs/`, configurar el `CLAUDE.md` institucional con la persona y las reglas, e indexar el código con CodeGraph.

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
- Si `.git/` no existe, **ofrecer `git init` inline** (una sola pregunta, sin insistir):

  > "No encontré un repositorio git. ¿Querés que corra `git init` ahora? (s/n)"

  Si el dev responde **s**: correr `git init`, reportarlo en el envelope (`git_initialized: true`).
  Si el dev responde **n** o no responde: continuar sin git init, reportar `git_initialized: false`. NO abortar ni repetir la oferta.

  **El código Python (`bootstrap.run()`) NO corre `git init`** — solo reporta si `.git/` existe. El consent es responsabilidad de la skill, no del Python.

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
    # /fg-plan paso 0 lo pregunta una vez por sesión y cachea la respuesta.
    cycle_mode: interactive

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

### 6. Generar o mergear `CLAUDE.md` institucional

- Si NO existe `CLAUDE.md` en la raíz: copiar el template `templates/CLAUDE-md-institucional.md` adaptando placeholders.
- Si existe: mergear secciones faltantes (persona, engram, mecánica TDD, workflow). NO sobrescribir secciones que el dev ya escribió. Reportar qué se mergeó.

### 7. Inicializar CodeGraph

- Verificar que el binario de CodeGraph esté disponible.
- Indexar el código actual del proyecto en `.codegraph/codegraph.db`.
- Reportar al dev la cantidad de nodos y aristas detectados.

### 8. Generar `.atl/skill-registry.md`

Escanear las skills disponibles para el proyecto: las propias de forge (`skills/*.md` instaladas globalmente o en el repo del proyecto), las del usuario en `~/.claude/skills/` (cualquier skill instalada por el dev en su máquina), y las de plugins activos de Claude Code. Generar el registry con compact rules pre-digeridas, siguiendo el protocolo de `_shared/skill-resolver.md`.

### 9. Actualizar `.gitignore`

- Agregar `.codegraph/` (ignorado completo).
- Agregar `.engram/` con excepción para `.engram/chunks/` (cross-machine memory).

Si el `.gitignore` ya tiene esas líneas, no duplicar.

### 10. Conversación de visión del sistema (solo en modo bootstrap)

Si `mode == bootstrap`, ejecutar este sub-flow. NO es una skill nueva — parte de `/fg-setup`.

Si `mode != bootstrap` → saltar todo el paso 10 y continuar al paso 11. Envelope: `vision_status: n/a`.

#### 10a. Idempotencia

Verificar antes de iniciar la conversación:

1. Si `docs/arquitectura/overview.md` ya existe → saltar el sub-flow, continuar al paso 11. Envelope: `vision_status: preserved`.
2. Si `config.yaml` tiene `context.vision_skipped: true` → preguntar una sola vez: "¿Querés intentar la conversación de visión de nuevo? [s/n]". Si "n" → saltar, continuar al paso 11. Si "s" → continuar al paso 10b.

#### 10b. 1ra ronda de preguntas

Iniciar la conversación con estas 5 preguntas (adaptar tono, mantener el foco):

1. ¿Qué es este sistema? ¿Quién lo usa? ¿Qué problema resuelve?
2. ¿Multi-tenant o single-tenant? Roles principales.
3. ¿Web / mobile / CLI / API pura? ¿Estrategia de autenticación?
4. Stack tecnológico: si el dev lo sabe, anotarlo; si no, decidir juntos.
5. Módulos o áreas principales previstas.

El dev puede saltar en cualquier momento respondiendo "saltar", "no" o "después" → ir directamente al paso 10d (skip path: `mark_vision_skipped`).

**Incluir SOLO lo que el dev mencionó. NO inventar módulos, integraciones, ni decisiones técnicas. Si algo no se mencionó, dejarlo fuera.**

#### 10c. 2da ronda de calibración (solo lo que falte)

Preguntar únicamente lo que el dev no mencionó en 10b:

- ¿Multi-tenant / single-tenant?
- ¿Roles dentro de cada tenant?
- ¿Web / mobile / ambos?
- ¿Stack (lenguaje, framework, DB, auth) — propuesta o decidir juntos?
- ¿Qué módulos prevés?

**NO inventar respuestas. Solo preguntar lo que el dev no mencionó.**

#### 10d. Destilar y validar

Construir drafts de `overview.md` y `stack.md` con **SOLO lo que el dev mencionó**. NO inventar módulos, decisiones técnicas ni roles no mencionados.

Mostrar ambos drafts en fenced blocks:

```markdown
# System Overview
[contenido destilado de la conversación]
```

```markdown
# Stack
[contenido destilado de la conversación]
```

Preguntar: `¿Aceptás estos drafts? [s/n/editar]`

- **`s`** → llamar `bootstrap.create_arquitectura_docs(root, overview_content, stack_content)`. Si el dev mencionó stacks durante la conversación, llamar también `bootstrap.patch_config_stacks(root, stacks)` y loguear en el envelope: "stacks actualizados en config.yaml: [<stack(s)>]". Agregar paths al envelope (`files_created` o `files_preserved` según lo retorne el helper). Envelope: `vision_status: completed`.
- **`editar`** → pedir al dev qué cambiar. Regenerar los drafts UNA SOLA VEZ y mostrarlos de nuevo. Aceptar solo `[s/n]` — NO ofrecer "editar" de nuevo (límite máx. 1 iteración de edición para evitar loops indefinidos). Si "n" después de la edición → ejecutar skip path.
- **`n`** (en cualquier punto) → skip path: llamar `bootstrap.mark_vision_skipped(root)`. Envelope: `vision_status: skipped`. Agregar a `envelope.warnings[]`: "Visión saltada — overview.md y stack.md no se generaron. Re-ejecutar /fg-setup o /fg-update-arch para crearlos."

Si el contexto LLM se agota antes de completar el paso 10d → no escribir archivos parciales, no patchear config. Envelope: `vision_status: incomplete` con advertencia explicando la interrupción.

### 11. Reportar al dev

Imprimir en español:

```
forge inicializado en modo: {modo}
forge instalado en {nombre del proyecto}

Stack detectado: {stack o "ninguno (bootstrap — re-detecta cuando agregues manifiestos)"}
Test runner: {comando ({nombre}, detectado de {manifiesto}) | "no detectado"}
CodeGraph: {N nodos, N aristas indexados | "no inicializado"}

Archivos generados/mergeados:
- CLAUDE.md ({creado | mergeado})
- docs/auditoria/config.yaml ({creado | preservado existente})
- config/modulos-transversales.yaml ({creado | preservado existente})
- .atl/skill-registry.md (generado)
- .gitignore (actualizado)

Nota: TDD está OFF por default. Para activarlo, editá docs/auditoria/config.yaml
      y cambiá rules.implement.tdd a true.
```

## Reglas

### Siempre

- Idempotente: re-ejecutar no rompe nada, solo agrega lo faltante.
- Mergear archivos pre-existentes (CLAUDE.md, gitignore, modulos-transversales.yaml) sin sobrescribir.
- Reportar al dev qué se hizo y qué se preservó.
- Generar `docs/auditoria/config.yaml` con la detección del paso 3 y defaults conservadores. NO sobrescribir si ya existe.
- NO activar Strict TDD desde `/fg-setup` — eso lo decide el dev editando el config a mano.

### Preguntar

- Si hay múltiples manifiestos (polyglot), preguntar cuál es el principal para CodeGraph.
- Si CodeGraph no está disponible, preguntar si seguir sin él (degradado) o instalarlo primero.
- Si `CLAUDE.md` ya existe y hay conflictos no triviales en el merge, mostrar el conflicto y dejar que el dev decida.

### Nunca

- Sobrescribir archivos existentes sin permiso.
- Generar scaffolding del proyecto (compose, Makefile, deploy/, src/, etc.).
- Preguntar por stack/perfil para imponer arquitectura.
- Crear `docs/arquitectura/` vacío — solo aparece con `/fg-update-arch`.
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
```
