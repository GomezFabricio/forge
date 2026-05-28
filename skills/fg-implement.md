---
name: fg-implement
description: Ejecuta el plan tarea por tarea siguiendo el ciclo de Strict TDD (Safety Net → Understand → RED → GREEN → TRIANGULATE → REFACTOR → Complete). Genera la TDD Cycle Evidence table como envelope de retorno para que /fg-review la valide.
when_to_apply: El dev invoca /fg-implement después de /fg-design. Es el tercer paso del workflow, donde se escribe el código.
---

# /fg-implement

## Propósito

Convertir el checklist de tareas del `design.md` en código que funciona, escrito bajo disciplina de TDD con triangulación. **El código es side effect de los tests** — los tests definen el comportamiento, la implementación pasa los tests.

## Cuándo aplicarla

Después de `/fg-design`, cuando el `design.md` tiene un checklist de tareas pendientes. Si no existe `design.md` o el checklist está vacío, abortar y sugerir correr `/fg-design` primero.

## Carga obligatoria del módulo Strict TDD

Si en `engram` existe `forge/testing-capabilities/{project}` con `strict_tdd: true`, cargar el módulo `_shared/strict-tdd.md` (vive en `mvp/skills/_shared/strict-tdd.md` cuando forge se instala). Ese módulo define el ciclo de 7 pasos, los banned assertion patterns, la regla extract-before-mock y approval testing.

Si `strict_tdd: false` (no se detectó test runner durante `/fg-setup`), correr en modo estándar (sin TDD obligatorio) y avisar al dev al inicio.

## Proceso

### 1. Leer el contexto del cambio

- Leer `design.md` del cambio activo, especialmente el Checklist y las Decisiones técnicas.
- Leer las testing capabilities cacheadas en engram (`mem_search` por `forge/testing-capabilities/{project}`).
- Si hay `apply-progress` previo en `design.md` (ej: vienes a continuar un cambio iniciado antes), retomar desde la primera tarea no tachada.

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
   Tachar la tarea en el checklist de design.md.

7. Note deviations
   Si surgió alguna decisión no anticipada durante el código, sumarla a Decisiones técnicas en design.md con fecha y razón.
   Si surgió un riesgo o tarea adicional, mencionarla al dev.
```

### 3. Sugerir invocar roles si el cambio toca áreas sensibles

`/fg-implement` NO invoca roles. Pero puede detectar contextos donde sugerir al dev (o a `/fg-review`) que se invoquen:

- Si el cambio toca código de autenticación, datos sensibles o endpoints públicos: anotar en `design.md` para que `/fg-review` invoque `security-reviewer`.
- Si el cambio crea migraciones o queries pesadas: anotar para `dba-reviewer`.

### 4. Manejar checklist completo

Cuando todas las tareas estén tachadas:

- Verificar que la suite completa de tests del cambio pase (no solo los nuevos).
- Generar la **TDD Cycle Evidence table** con una fila por tarea (ver formato en `_shared/strict-tdd.md`).
- Actualizar el campo Estado del `README.md` a `implementado`.

### 5. Reportar al dev

- Confirmar implementación completa o reportar tareas no terminadas.
- Mostrar la TDD Cycle Evidence table al user (será el insumo principal de `/fg-review`).
- Sugerir el siguiente paso: `/fg-review`.

## Reglas (Strict TDD)

### Siempre

- NUNCA escribir código de producción sin un test fallando primero. Esta es la regla irrompible.
- Ejecutar el test después de GREEN y confirmar que pasa antes de avanzar.
- Triangulación es default — no saltar.
- Correr SAFETY NET antes de modificar archivos pre-existentes.
- Reportar la TDD Cycle Evidence table al cerrar.
- Cuando el spec define múltiples scenarios, escribir test cases que los cubran todos.
- Cuando aparece una decisión durante el código, registrarla en `design.md` y avisar al dev.

### Preguntar

- Cuando una decisión técnica no anticipada bloquea el avance.
- Cuando un test falla por razones que parecen ajenas al cambio (puede ser pre-existing failure que requiere intervención).

### Nunca

- Saltar la triangulación cuando hay múltiples scenarios en el spec.
- Escribir tautologías (`expect(true).toBe(true)`), empty collection sin compañero, type-only assertions solas, ghost loops, smoke tests sin behavioral, CSS class assertions, mock-heavy tests (>2× expect).
- Modificar tests para que pasen (eso oculta bugs reales).
- Arreglar pre-existing failures detectados en SAFETY NET (reportar al dev, no arreglar acá).
- Saltar a `/fg-review` con tareas sin terminar y sin reportarlas como bloqueadas.

## Envelope de retorno

```yaml
status: success | partial | blocked
executive_summary: 1-2 oraciones de lo que se implementó
artifacts:
  - <lista de archivos creados/modificados>
  - docs/changes/<cambio>/fg-design.md (checklist actualizado, decisiones agregadas)
  - docs/changes/<cambio>/README.md (Estado: implementado o implementando)
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
next_recommended: /fg-review
risks: None | <riesgos detectados>
flags_for_review:
  - <ej: "toca auth, sugerir security-reviewer">
  - <ej: "tiene migraciones, sugerir dba-reviewer">
```
