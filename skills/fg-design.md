---
name: fg-design
description: Define el cómo del cambio. Lee el README.md generado por /fg-plan, consulta CodeGraph para identificar archivos afectados realmente, y produce tres documentos (diseño.md, tareas.md, decisiones.md) con enfoque técnico, arquitectura, archivos, checklist de tareas y decisiones técnicas iniciales.
when_to_apply: El dev invoca /fg-design después de haber corrido /fg-plan. Es el segundo paso del workflow.
---

> Cargar antes: `skills/_shared/fg-phase-common.md` (secciones A, B, C, E)

# /fg-design

## Propósito

Convertir el qué/por qué del `README.md` en un plan técnico ejecutable. La salida son tres archivos bajo `docs/auditoria/cambios/<cambio>/`: `diseño.md` (documento estable con enfoque, arquitectura y archivos afectados), `tareas.md` (checklist mutable durante `/fg-implement`) y `decisiones.md` (registro append-only de decisiones técnicas).

## Cuándo aplicarla

Después de `/fg-plan`, cuando el dev quiere definir cómo se va a implementar el cambio. Si no existe `README.md` del cambio, abortar y sugerir correr `/fg-plan` primero.

## Proceso

### 1. Leer el contexto del cambio

- Leer `README.md` del cambio activo (sección Qué, Por qué, Alcance, Restricciones).
- Si no hay un cambio activo claro, preguntar al dev cuál.

### 2. Consultar CodeGraph para identificar archivos afectados realmente

Con la información del `README.md`, consultar el índice de CodeGraph para responder:

- ¿Qué archivos del codebase contienen lógica relacionada con el cambio?
- ¿Hay clases, funciones o módulos que claramente se tocan?
- ¿Hay archivos que el cambio probablemente NO toca pero el dev podría pensar que sí?

La idea es **no adivinar** archivos afectados con grep textual; usar el grafo estructural que CodeGraph ya indexó.

### 3. Definir el enfoque técnico

En la sección "Enfoque" de `diseño.md`, escribir:

- Estrategia general (ej: "agregar un nuevo módulo `auth/` con servicios separados", "extender el endpoint existente con un nuevo parámetro").
- Librerías o tools que se van a usar y por qué (ej: "bcrypt para hashing porque ya está en el proyecto").
- Patrones que se siguen (ej: "mismo patrón que el módulo `users/`").

Si hay decisiones técnicas grandes que NO son obvias del contexto, preguntarlas al dev y registrarlas en la sección "Decisiones técnicas".

### 4. Documentar la arquitectura

En la sección "Arquitectura" de `diseño.md`:

- Cómo el cambio se integra con el sistema existente.
- Diagramas simples en formato mermaid si el cambio cruza varios módulos.
- Contratos de interfaz (signatures de funciones nuevas, schemas de endpoints, etc.).

### 5. Listar archivos afectados

En la sección "Archivos afectados" de `diseño.md`, listar paths concretos con marca de nuevo/modificado/eliminado. Usar la información del paso 2 (CodeGraph), no inventar.

Ejemplo:
```
- src/auth/login.py            (nuevo)
- src/auth/__init__.py         (modificado)
- src/api/routes.py            (modificado)
- tests/auth/test_login.py     (nuevo)
- migrations/00X_users.sql     (nuevo)
```

### 6. Descomponer en checklist de tareas

En `tareas.md`, listar tareas concretas marcables bajo la sección "Checklist de tareas".

Reglas para la descomposición:

- Cada tarea debe ser ejecutable en una pasada de TDD (RED → GREEN → TRIANGULATE → REFACTOR).
- Granularidad: ni demasiado fino (1 línea por tarea) ni demasiado grueso (1 tarea = todo el cambio).
- Cada tarea debe describir un comportamiento testeable.
- Orden lógico: dependencias primero, integración después.

Ejemplo:
```
- [ ] Crear schema de la tabla users con migración SQL
- [ ] Implementar servicio de hashing de password (función pura)
- [ ] Implementar servicio de validación de credenciales
- [ ] Implementar endpoint POST /login
- [ ] Manejar caso de credenciales inválidas (401)
- [ ] Manejar caso de usuario ya con sesión activa
- [ ] Integration test del flujo completo de login
```

### 7. Registrar decisiones técnicas iniciales

En `decisiones.md` (append-only — nunca sobrescribir):

- Cualquier decisión grande que se tomó durante `/fg-design` (elección de librería, patrón arquitectónico, contrato de API).
- Cada decisión: fecha (YYYY-MM-DD) + qué se decidió + por qué.

Ejemplo:
```
- 2026-05-26: Usamos bcrypt sobre argon2. Razón: bcrypt ya está en el proyecto y satisface el threat model interno.
```

`decisiones.md` crece durante `/fg-implement` con decisiones que surjan en el código — siempre append, nunca rewrite.

### 8. Emitir el Review Workload Forecast

Aplicar la lógica de la **Sección C** de `fg-phase-common.md` (cargada al inicio):

1. Leer `rules.pr_size.enforcement` de `docs/auditoria/config.yaml`.
2. Si `enforcement: off`, saltar este paso completamente.
3. Si `enforcement: warn` o `block`:
   - Estimar `estimated_changed_lines` sumando los archivos de "Archivos afectados" de `diseño.md`.
   - Calcular `budget_risk` (Low / Medium / High) según el umbral `rules.pr_size.budget_lines`.
   - Emitir el bloque de texto con las guard lines exactas (ver Sección C).
   - Si `enforcement: block` y el riesgo es High: pedir al dev `size:exception` documentada antes de continuar.

El campo `review_workload_forecast` se incluye en el envelope de retorno.

### 9. Actualizar el README.md

Cambiar la sección "Estado" del `README.md` a `diseñado`.

### 10. Reportar al dev

- Confirmar los tres archivos creados: `diseño.md`, `tareas.md`, `decisiones.md`.
- Si alguno ya existe, NO sobrescribir — preguntar al dev si quiere re-correr `/fg-design` (caso re-diseño parcial).
- Mostrar la cantidad de tareas del checklist de `tareas.md`.
- Sugerir el siguiente paso: `/fg-implement`.

## Reglas

### Siempre

- Leer el `README.md` del cambio antes de empezar.
- Consultar CodeGraph para identificar archivos afectados reales.
- Crear los tres archivos (`diseño.md`, `tareas.md`, `decisiones.md`) desde los templates correspondientes.
- Escribir todos los artefactos en español.
- Cada decisión técnica registrada en `decisiones.md` con fecha y razón.
- El checklist de `tareas.md` debe estar ordenado: dependencias primero.

### Preguntar

- Cuando una decisión técnica tiene varias opciones razonables sin una clara preferencia (ej: dos librerías equivalentes ya en el proyecto).
- Cuando el alcance del README es ambiguo a nivel arquitectónico.
- Cuando CodeGraph sugiere archivos afectados que NO estaban implícitos en el README.

### Nunca

- Inventar archivos afectados sin consultar CodeGraph.
- Imponer un patrón arquitectónico que el proyecto no usa.
- Saltarse la creación de `decisiones.md` (aunque esté vacío, debe existir).
- Empezar a escribir código del cambio (eso es `/fg-implement`).
- Modificar el `README.md` excepto por el campo Estado.
- Sobrescribir archivos existentes — si alguno de los tres ya existe, preguntar al dev.

## Envelope de retorno

```yaml
status: success | partial | blocked
executive_summary: 1-2 oraciones de lo que se diseñó
artifacts:
  - docs/auditoria/cambios/<cambio>/diseño.md (creado)
  - docs/auditoria/cambios/<cambio>/tareas.md (creado)
  - docs/auditoria/cambios/<cambio>/decisiones.md (creado)
  - docs/auditoria/cambios/<cambio>/README.md (actualizado, Estado: diseñado)
tasks_count: <cantidad de tareas en el checklist>
files_affected:
  - <lista de archivos identificados con CodeGraph>
decisiones_grandes:
  - <decisiones técnicas registradas durante /fg-design>
review_workload_forecast:
  estimated_changed_lines: <N>
  budget_threshold: <budget_lines del config>
  budget_risk: Low | Medium | High
  chained_recommended: Yes | No
  decision_needed_before_apply: Yes | No
  suggested_split: <descripción o "none">
next_recommended: /fg-implement
risks: None | <riesgos técnicos detectados>
skill_resolution: paths-injected | fallback-registry | none
```
