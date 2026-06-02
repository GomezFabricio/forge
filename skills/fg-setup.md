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
- No crea `docs/arquitectura/` vacío — esa carpeta aparece a demanda con `/fg-update-arch`.

## Cuándo aplicarla

- Una vez al incorporar forge a un proyecto.
- Re-invocable para upgrade: detecta lo existente, mergea archivos sin sobrescribir, solo agrega lo faltante. Idempotente.

## Proceso

### 1. Verificar contexto del proyecto

- Confirmar que el directorio actual es la raíz de un proyecto (existe `.git/`, o un manifiesto reconocido como `pyproject.toml`, `package.json`, `go.mod`, etc.).
- Si no parece un proyecto, abortar y avisar al dev.

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

### 10. Reportar al dev

Imprimir en español:

```
forge instalado en {nombre del proyecto}

Stack detectado: {stack}
Test runner: {comando} ({nombre}, detectado de {manifiesto})
CodeGraph: {N nodos, N aristas indexados}

Archivos generados/mergeados:
- CLAUDE.md ({creado | mergeado})
- docs/auditoria/config.yaml ({creado | preservado existente})
- config/modulos-transversales.yaml ({creado | preservado existente})
- .atl/skill-registry.md (generado)
- .gitignore (actualizado)

Nota: TDD está OFF por default. Para activarlo, editá docs/auditoria/config.yaml
      y cambiá rules.implement.tdd a true.

Próximo paso: /fg-plan <descripción del cambio que querés hacer>
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
stack_detected: <stack>
test_runner: <comando o "no detectado">
audit_config: created | preserved
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
next_recommended: /fg-plan <descripción>
```
