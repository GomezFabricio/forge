---
name: fg-design
description: Define el cómo del cambio. Lee el README.md generado por /fg-plan, consulta CodeGraph para identificar archivos afectados realmente, y produce design.md con enfoque técnico, arquitectura, archivos, checklist de tareas y decisiones técnicas iniciales.
when_to_apply: El dev invoca /fg-design después de haber corrido /fg-plan. Es el segundo paso del workflow.
---

# /fg-design

## Propósito

Convertir el qué/por qué del `README.md` en un plan técnico ejecutable. La salida es `design.md`, un documento vivo que crece durante `/fg-implement` registrando decisiones que surgen.

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

En la sección "Enfoque" del `design.md`, escribir:

- Estrategia general (ej: "agregar un nuevo módulo `auth/` con servicios separados", "extender el endpoint existente con un nuevo parámetro").
- Librerías o tools que se van a usar y por qué (ej: "bcrypt para hashing porque ya está en el proyecto").
- Patrones que se siguen (ej: "mismo patrón que el módulo `users/`").

Si hay decisiones técnicas grandes que NO son obvias del contexto, preguntarlas al dev y registrarlas en la sección "Decisiones técnicas".

### 4. Documentar la arquitectura

En la sección "Arquitectura":

- Cómo el cambio se integra con el sistema existente.
- Diagramas simples en formato mermaid si el cambio cruza varios módulos.
- Contratos de interfaz (signatures de funciones nuevas, schemas de endpoints, etc.).

### 5. Listar archivos afectados

En la sección "Archivos afectados", listar paths concretos con marca de nuevo/modificado/eliminado. Usar la información del paso 2 (CodeGraph), no inventar.

Ejemplo:
```
- src/auth/login.py            (nuevo)
- src/auth/__init__.py         (modificado)
- src/api/routes.py            (modificado)
- tests/auth/test_login.py     (nuevo)
- migrations/00X_users.sql     (nuevo)
```

### 6. Descomponer en checklist de tareas

En la sección "Checklist de tareas", listar tareas concretas marcables.

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

En la sección "Decisiones técnicas":

- Cualquier decisión grande que se tomó durante `/fg-design` (elección de librería, patrón arquitectónico, contrato de API).
- Cada decisión: fecha (YYYY-MM-DD) + qué se decidió + por qué.

Ejemplo:
```
- 2026-05-26: Usamos bcrypt sobre argon2. Razón: bcrypt ya está en el proyecto y satisface el threat model interno.
```

Esta sección crece durante `/fg-implement` con decisiones que surjan en el código.

### 8. Actualizar el README.md

Cambiar la sección "Estado" del `README.md` a `diseñado`.

### 9. Reportar al dev

- Confirmar `design.md` creado.
- Mostrar la cantidad de tareas del checklist.
- Sugerir el siguiente paso: `/fg-implement`.

## Reglas

### Siempre

- Leer el `README.md` del cambio antes de empezar.
- Consultar CodeGraph para identificar archivos afectados reales.
- Escribir el `design.md` en español.
- Cada decisión técnica registrada con fecha y razón.
- El checklist debe estar ordenado: dependencias primero.

### Preguntar

- Cuando una decisión técnica tiene varias opciones razonables sin una clara preferencia (ej: dos librerías equivalentes ya en el proyecto).
- Cuando el alcance del README es ambiguo a nivel arquitectónico.
- Cuando CodeGraph sugiere archivos afectados que NO estaban implícitos en el README.

### Nunca

- Inventar archivos afectados sin consultar CodeGraph.
- Imponer un patrón arquitectónico que el proyecto no usa.
- Saltarse la sección Decisiones técnicas (aunque esté vacía, debe existir).
- Empezar a escribir código del cambio (eso es `/fg-implement`).
- Modificar el `README.md` excepto por el campo Estado.

## Envelope de retorno

```yaml
status: success | partial | blocked
executive_summary: 1-2 oraciones de lo que se diseñó
artifacts:
  - docs/audit/changes/<cambio>/fg-design.md (creado)
  - docs/audit/changes/<cambio>/README.md (actualizado, Estado: diseñado)
tasks_count: <cantidad de tareas en el checklist>
files_affected:
  - <lista de archivos identificados con CodeGraph>
decisiones_grandes:
  - <decisiones técnicas registradas durante /fg-design>
next_recommended: /fg-implement
risks: None | <riesgos técnicos detectados>
```
