---
name: fg-implement
description: Ejecuta el plan tarea por tarea siguiendo el ciclo de Strict TDD (Safety Net → Understand → RED → GREEN → TRIANGULATE → REFACTOR → Complete). Genera la TDD Cycle Evidence table como envelope de retorno para que /fg-review la valide.
when_to_apply: El dev invoca /fg-implement después de /fg-design. Es el tercer paso del workflow, donde se escribe el código.
---

> **ORCHESTRATOR GATE**: Si cargaste esta skill vía la tool `Skill`, sos el ORQUESTADOR — STOP.
> NO ejecutes estas instrucciones inline. Delegá al sub-agente `fg-implement` usando la primitiva
> de delegación de tu plataforma (ej. la tool `Task` o el sub-agente nativo). Esta skill es
> solo para EXECUTORS.

## Executor Override

Si SOS el sub-agente `fg-implement` (NO el orquestador), el gate de arriba NO aplica. Continuá con
el trabajo de la fase que sigue. NO delegues. NO llamés a la tool `Skill`. NO llamés a la tool
`Task`. Sos el executor — ejecutá.

> Cargar antes: `skills/_shared/fg-phase-common.md` (secciones A, B, E)

# /fg-implement

## Propósito

Convertir el checklist de tareas de `tareas.md` en código que funciona, escrito bajo disciplina de TDD con triangulación. **El código es side effect de los tests** — los tests definen el comportamiento, la implementación pasa los tests.

## Cuándo aplicarla

Después de `/fg-design`, cuando `tareas.md` tiene un checklist de tareas pendientes. Si no existe `tareas.md` o el checklist está vacío, abortar y sugerir correr `/fg-design` primero.

## Carga obligatoria del módulo Strict TDD

Leer `docs/auditoria/config.yaml` del proyecto. Si `rules.implement.tdd` es `true`, cargar el módulo `_shared/strict-tdd.md`. Ese módulo define el ciclo de 7 pasos, los banned assertion patterns, la regla extract-before-mock y approval testing.

Si `rules.implement.tdd` es `false` (default que viene de `/fg-setup`), correr en modo estándar (sin TDD obligatorio) y avisar al dev al inicio que el ciclo TDD no está activo. El dev puede activarlo editando `docs/auditoria/config.yaml` y reenviando.

El comando de test a usar es `rules.implement.test_command`. Si está vacío, fallback a `context.test_runner.command`. Si los dos están vacíos, abortar con mensaje claro al dev.

## Proceso

### 1. Leer el contexto del cambio

> `diseño.md` es **opcional**; `tareas.md` es **obligatorio**.

- Leer `tareas.md` para el checklist de tareas a ejecutar. Si no existe, abortar y sugerir correr `/fg-design` (o `/fg-plan` en modo Rápido) primero.
- Leer `diseño.md` del cambio activo para entender el enfoque y la arquitectura.
  Si `diseño.md` **no existe** (escenario de modo Rápido — el orquestador determinó que no aplica `/fg-design`):
  - No abortar ni advertir — es un caso válido.
  - Usar el `README.md` del cambio como contexto de enfoque en su lugar.
  - El contrato de lectura de `tareas.md` no cambia.
- Leer `docs/auditoria/config.yaml` del proyecto para conocer el modo TDD y el comando de test.
- Si hay tareas ya tachadas en `tareas.md` (ej: vienes a continuar un cambio iniciado antes), retomar desde la primera tarea no tachada.

### 1b. Verificar y retomar progreso anterior (pattern de batching)

Aplicar la lógica de la **Sección E.5** de `fg-phase-common.md` (cargada al inicio):

1. Buscar progreso previo en engram: `mem_search(query: "forge/{cambio}/implement-progress", project: "{project}")`.
2. Si existe: `mem_get_observation(id)` → parsear tareas ya marcadas `[x]` → retomarlas como completadas.
3. Contar las tareas pendientes (no completadas) en `tareas.md`.
4. Leer `rules.implement.max_tasks_per_batch` de `docs/auditoria/config.yaml` (default: 20 si no está configurado).
5. Si las tareas pendientes superan `max_tasks_per_batch`:
   - Implementar solo hasta llegar al límite del batch.
   - Al finalizar el batch: guardar progreso mergeando (ver regla E.5 — NUNCA overwrite).
   - Reportar al dev: "Implementé N tareas. Quedan X pendientes. Re-invocá `/fg-implement` para continuar (idealmente en sesión nueva)."
6. Si las tareas pendientes caben en el batch: continuar hasta completar todas.

### 2. Ejecutar el ciclo TDD para cada tarea

Para cada tarea del checklist en orden, aplicar el ciclo completo de 7 pasos:

```
0. SAFETY NET (solo si modifica archivos existentes)
   Correr los tests pre-existentes de esos archivos.
   Si pasan: continuar.
   Si fallan: STOP y reportar al dev como "pre-existing failure" — NO arreglar fallas pre-existentes acá.

1. UNDERSTAND
   Releer la tarea, el spec asociado (si existe), el design, código existente, patrones de tests del proyecto.
   Decidir test layer (Unit / Integration / E2E) según las testing capabilities y el tipo de tarea.

2. RED — Test fallando primero
   Escribir el test que describe el comportamiento esperado.
   El test debe referenciar código de producción que NO existe aún.
   No ejecutar el test todavía — el solo hecho de que el código referenciado no exista garantiza el fallo.
   GATE: no avanzar a GREEN sin RED escrito.

3. GREEN — Código mínimo que pasa
   Escribir el mínimo código de producción necesario para que el test pase.
   "Fake It" es válido (return hardcodeado).
   EJECUTAR el test → debe PASAR.
   GATE: no avanzar a TRIANGULATE sin GREEN confirmado por ejecución real.

4. TRIANGULATE — Forzar lógica real
   Agregar un segundo test case con inputs distintos al primero.
   Ejecutar → si el Fake It no funciona para el segundo caso, generalizar la lógica.
   MÍNIMO: 2 test cases (happy path + un edge case distinto).
   Skip solo si la tarea es estructural pura (definición de constante, type export), documentando razón en la evidencia.

5. REFACTOR — Mejorar sin cambiar comportamiento
   Extraer constants, funciones puras, eliminar duplicación.
   Ejecutar tests después de CADA refactor — deben seguir verdes.
   Si un refactor rompe tests: revertir ese paso, intentar más chico.

6. Mark task complete
   Tachar la tarea en el checklist de tareas.md.

7. Note deviations
   Si surgió alguna decisión no anticipada durante el código, agregarla al final de decisiones.md con fecha y razón (append-only — nunca sobrescribir).
   Si surgió un riesgo o tarea adicional, mencionarla al dev.
```

### 3. Sugerir invocar roles si el cambio toca áreas sensibles

`/fg-implement` NO invoca roles. Pero puede detectar contextos donde sugerir al dev (o a `/fg-review`) que se invoquen:

- Si el cambio toca código de autenticación, datos sensibles o endpoints públicos: anotar en `decisiones.md` para que `/fg-review` invoque `security-reviewer`.
- Si el cambio crea migraciones o queries pesadas: anotar para `dba-reviewer`.

### 4. Manejar checklist completo

Cuando todas las tareas estén tachadas:

- Verificar que la suite completa de tests del cambio pase (no solo los nuevos).
- Generar la **TDD Cycle Evidence table** con una fila por tarea (ver formato en `_shared/strict-tdd.md`).
- Persistir la evidencia en disco escribiendo `docs/auditoria/cambios/<cambio>/evidencia-tdd.md`:
  - Si el archivo **no existe**: crearlo con la tabla completa y el resumen de tests (usando el template en `templates/evidencia-tdd.md`).
  - Si el archivo **ya existe** (continuación de batch previo): leerlo, mergear las filas nuevas al final de la tabla y actualizar el resumen de tests. **NUNCA sobreescribir — siempre mergear.**
  - El contenido del archivo es la misma tabla que se incluye en el envelope: una fila por tarea con columnas Safety Net / RED / GREEN / TRIANGULATE / REFACTOR, más el resumen de tests al pie.
- Actualizar el campo Estado del `README.md` a `implementado`.

### 5. Reportar al dev

- Confirmar implementación completa o reportar tareas no terminadas.
- Mostrar la TDD Cycle Evidence table al user (será el insumo principal de `/fg-review`).
- Confirmar que `evidencia-tdd.md` fue escrito (o mergeado) en la carpeta del cambio.
- Sugerir el siguiente paso: `/fg-review`.

## Reglas (Strict TDD)

### Siempre

- NUNCA escribir código de producción sin un test fallando primero. Esta es la regla irrompible.
- Ejecutar el test después de GREEN y confirmar que pasa antes de avanzar.
- Triangulación es default — no saltar.
- Correr SAFETY NET antes de modificar archivos pre-existentes.
- Reportar la TDD Cycle Evidence table al cerrar.
- Cuando el spec define múltiples scenarios, escribir test cases que los cubran todos.
- Cuando aparece una decisión durante el código, agregarla al final de `decisiones.md` (append-only) y avisar al dev.

### Preguntar

- Cuando una decisión técnica no anticipada bloquea el avance.
- Cuando un test falla por razones que parecen ajenas al cambio (puede ser pre-existing failure que requiere intervención).

### Nunca

- Saltar la triangulación cuando hay múltiples scenarios en el spec.
- Escribir tautologías (`expect(true).toBe(true)`), empty collection sin compañero, type-only assertions solas, ghost loops, smoke tests sin behavioral, CSS class assertions, mock-heavy tests (>2× expect).
- Modificar tests para que pasen (eso oculta bugs reales).
- Arreglar pre-existing failures detectados en SAFETY NET (reportar al dev, no arreglar acá).
- Saltar a `/fg-review` con tareas sin terminar y sin reportarlas como bloqueadas.

### TRIGGER B — Consulta selectiva de Context7 ante duda explícita de API externa

Si durante la implementación hay **ambigüedad real** sobre la firma, los parámetros o el comportamiento de una API de librería **EXTERNA** (no del propio codebase), consultar Context7 **antes de inventar la firma**:

1. `mcp__context7__resolve-library-id` con el nombre de la librería → ID canónico.
2. `mcp__context7__get-library-docs` con el ID y la query sobre el aspecto dudoso.

**Reglas de uso**:
- 1 par de llamadas por duda concreta, no en bucle.
- Solo para librerías externas. No consultar para APIs del propio codebase ni cuando la firma es conocida.
- Citar la fuente de documentación en el output al dev cuando se usa Context7.
- Si Context7 no responde: continuar con la mejor estimación disponible y documentar la incertidumbre.

**Privacidad**: solo viajan el nombre de la librería y la query. El código del dev nunca sale del entorno local.

## Envelope de retorno

```yaml
status: success | partial | blocked
executive_summary: 1-2 oraciones de lo que se implementó
artifacts:
  - <lista de archivos creados/modificados>
  - docs/auditoria/cambios/<cambio>/tareas.md (checklist actualizado)
  - docs/auditoria/cambios/<cambio>/decisiones.md (decisiones nuevas agregadas, si las hubo)
  - docs/auditoria/cambios/<cambio>/README.md (Estado: implementado o implementando)
  - docs/auditoria/cambios/<cambio>/evidencia-tdd.md (creado o mergeado; solo si TDD activo)
tdd_cycle_evidence:
  # Tabla con una fila por tarea (ver formato en _shared/strict-tdd.md)
  - task: <id o título>
    test_file: <path>
    layer: Unit | Integration | E2E
    safety_net: ✅ N/N | N/A (new)
    red: ✅ Written
    green: ✅ Passed
    triangulate: ✅ N cases | ➖ Single
    refactor: ✅ Clean | ➖ None needed
tests_summary:
  total_written: <N>
  total_passing: <N>
  layers: Unit (<N>), Integration (<N>), E2E (<N>)
batch_status:
  tasks_completed_this_batch: <N>
  tasks_remaining: <N>
  continue_needed: true | false    # true si quedan tareas para el próximo batch
next_recommended: /fg-review (si continue_needed=false) | /fg-implement (si continue_needed=true)
risks: None | <riesgos detectados>
flags_for_review:
  - <ej: "toca auth, sugerir security-reviewer">
  - <ej: "tiene migraciones, sugerir dba-reviewer">
skill_resolution: paths-injected | fallback-registry | none
```
