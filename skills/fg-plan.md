---
name: fg-plan
description: Entiende un cambio nuevo. El dev describe lo que quiere hacer en lenguaje natural y la skill infiere tipo, nombre kebab-case, contexto del codebase y genera el README inicial del cambio.
when_to_apply: El dev invoca /fg-plan con una descripción libre en lenguaje natural. Es el primer paso del workflow de cualquier cambio nuevo.
---

# /fg-plan

## Propósito

Convertir una idea expresada en lenguaje natural en una carpeta de cambio bien estructurada, con un `README.md` inicial que captura el qué, el por qué, el alcance y las restricciones. **Cero fricción de naming**: el dev no tiene que recordar la convención de tipos ni inventar nombres kebab-case — la skill lo infiere.

## Cuándo aplicarla

El dev invoca `/fg-plan` seguido de una descripción libre. Ejemplos:

- `/fg-plan login de usuarios`
- `/fg-plan arreglar el bug del rate limit del endpoint de búsqueda`
- `/fg-plan migrar el módulo de notificaciones a una librería externa`
- `/fg-plan optimizar el query del listado de expedientes`

Si el dev quiere forzar el tipo y nombre exactos, puede usar la sintaxis explícita `tipo:nombre descripción`. Ejemplo: `/fg-plan feat:login-oauth login con OAuth2`. Solo es necesario cuando se quiere precisión absoluta.

## Proceso

### 1. Inferir el tipo del cambio

Aplicar las siguientes heurísticas sobre la descripción del dev. El tipo final debe ser uno de: `feat`, `fix`, `refactor`, `chore`, `docs`, `perf`, `test`.

| Si la descripción menciona... | Tipo inferido |
|---|---|
| "arreglar", "bug", "error", "no funciona", "falla" | `fix` |
| "migrar", "refactorizar", "limpiar", "mejorar estructura", "reescribir" | `refactor` |
| "documentar", "agregar guía", "actualizar docs" | `docs` |
| "optimizar", "performance", "más rápido", "lento" | `perf` |
| "agregar tests", "cobertura", "test que falta" | `test` |
| Configuración, dependencias, scripts internos | `chore` |
| Feature nueva o no claramente categorizable | `feat` |

### 2. Inferir el nombre en kebab-case

- Extraer las palabras clave significativas de la descripción.
- Eliminar conectores en español ("de", "para", "el", "la", "los", "las", "un", "una", "y", "o", "en", "del").
- Convertir a kebab-case (minúsculas separadas por guiones).
- Limitar a 4-5 palabras significativas.

Ejemplos:
- "login de usuarios" → `login-usuarios`
- "arreglar el bug del rate limit" → `rate-limit-bug`
- "optimizar el query del listado de expedientes" → `optimizar-query-listado-expedientes`

### 3. Validar inferencia ambigua

Si una de las inferencias no es clara (la descripción podría caer en dos tipos, o el nombre tiene múltiples interpretaciones razonables), preguntar al dev antes de continuar. Mentor cordial: stop on confusion, never assume.

Ejemplo de pregunta:
> "La descripción podría ser `feat-login-usuarios` (sistema nuevo) o `refactor-login-existente` (refactor del actual). ¿Cuál corresponde?"

### 4. Crear la carpeta del cambio

Path: `docs/changes/<YYYY-MM>-<tipo>-<nombre>/`

Donde `<YYYY-MM>` es el año-mes actual.

Ejemplo: `docs/changes/2026-05-feat-login-usuarios/`

### 5. Consultar CodeGraph para entender el contexto

Antes de escribir el `README.md`, consultar el índice de CodeGraph para responder:

- ¿Qué módulos del codebase están relacionados con el cambio?
- ¿Hay entidades de dominio existentes que el cambio toca?
- ¿Hay dependencias entre módulos que el dev debería conocer?

Esta información se usa para enriquecer el `README.md` y para preguntarle al dev cuestiones específicas si algo no queda claro del prompt original.

### 6. Preguntar lo que no quede claro del problema

NO preguntar sobre el naming (eso se infiere). Preguntar sobre el problema en sí: alcance, restricciones técnicas, dependencias con otros equipos, criterios de aceptación, etc.

Ejemplos de preguntas válidas:
- "¿El login debe soportar OAuth o solo usuario/contraseña?"
- "¿Hay algún endpoint existente que reemplazar, o es completamente nuevo?"
- "¿Qué pasa si el usuario ya tiene una sesión activa?"

### 7. Generar el README.md inicial

Usar el template `templates/README-change.md`. Rellenar las secciones:

- **Qué**: 1-2 párrafos sobre qué problema resuelve el cambio.
- **Por qué**: contexto y motivación.
- **Alcance**: qué entra, qué queda explícitamente afuera.
- **Restricciones**: limitaciones técnicas, de tiempo, dependencias con otros equipos.
- **Estado**: `planeado`.

Dejar la sección **Cierre** vacía — la rellena `/fg-review` al final.

### 8. Reportar al dev

Imprimir:
1. Ruta de la carpeta creada.
2. Tipo y nombre inferidos.
3. Sugerir el siguiente paso: `/fg-design`.

## Reglas

### Siempre

- Inferir tipo y nombre del lenguaje natural del dev.
- Consultar CodeGraph para enriquecer el contexto antes de escribir.
- Preguntar sobre el problema cuando algo no quede claro.
- Escribir el `README.md` en español.
- Usar `YYYY-MM` (año-mes) en el nombre de la carpeta, NO `YYYY-MM-DD`.

### Preguntar

- Solo cuando la inferencia de tipo o nombre sea genuinamente ambigua.
- Solo cuando el alcance del problema tenga huecos importantes que afecten el diseño.

### Nunca

- Pedirle al dev que escriba el tipo o el nombre en kebab-case por su cuenta.
- Asumir alcance o restricciones que el dev no mencionó. Si no se sabe, preguntar.
- Crear el `design.md` (ese lo crea `/fg-design`).
- Tocar código del proyecto.
- Imponer estilos de arquitectura o stack.

## Envelope de retorno

```yaml
status: success | partial | blocked
executive_summary: 1-2 oraciones de lo que se hizo
artifacts:
  - docs/changes/<YYYY-MM>-<tipo>-<nombre>/README.md
inferred:
  tipo: <tipo inferido>
  nombre: <nombre kebab-case inferido>
next_recommended: /fg-design
risks: None | <riesgos detectados durante la conversación>
```
