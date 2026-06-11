---
name: fg-plan
description: Entiende un cambio nuevo. El dev describe lo que quiere hacer en lenguaje natural y la skill infiere tipo, nombre kebab-case, contexto del codebase y genera el README inicial del cambio.
when_to_apply: El dev invoca /fg-plan con una descripción libre en lenguaje natural. Es el primer paso del workflow de cualquier cambio nuevo. El nivel de ceremonia ya fue determinado por el orquestador antes de invocar esta skill.
---

> **ORCHESTRATOR GATE**: Si cargaste esta skill vía la tool `Skill`, sos el ORQUESTADOR — STOP.
> NO ejecutes estas instrucciones inline. Delegá al sub-agente `fg-plan` usando la primitiva
> de delegación de tu plataforma (ej. la tool `Task` o el sub-agente nativo). Esta skill es
> solo para EXECUTORS.

## Executor Override

Si SOS el sub-agente `fg-plan` (NO el orquestador), el gate de arriba NO aplica. Continuá con
el trabajo de la fase que sigue. NO delegues. NO llamés a la tool `Skill`. NO llamés a la tool
`Task`. Sos el executor — ejecutá.

> Cargar antes: `skills/_shared/fg-phase-common.md` (secciones A, B, D, E)

# /fg-plan

## Propósito

Convertir una idea expresada en lenguaje natural en una carpeta de cambio bien estructurada, con un `README.md` inicial que captura el qué, el por qué, el alcance y las restricciones. **Cero fricción de naming**: el dev no tiene que recordar la convención de tipos ni inventar nombres kebab-case — la skill lo infiere.

## Cuándo aplicarla

El dev invoca `/fg-plan` seguido de una descripción libre. Ejemplos:

- `/fg-plan login de usuarios`
- `/fg-plan arreglar el bug del rate limit del endpoint de búsqueda`
- `/fg-plan migrar el módulo de notificaciones a una librería externa`
- `/fg-plan optimizar el query del listado de expedientes`
- `/fg-plan --from docs/prd.md "implementar login de usuarios"`

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

Path: `docs/auditoria/cambios/<YYYY-MM>-<tipo>-<nombre>/`

Donde `<YYYY-MM>` es el año-mes actual.

Ejemplo: `docs/auditoria/cambios/2026-05-feat-login-usuarios/`

### 5. Resolver contexto (Branch 1, 2, 3a, 3b, o 3c)

El contexto de un cambio puede venir de tres fuentes en orden de prioridad: doc externa explícita (`--from`), overview de arquitectura, o análisis de código vía CodeGraph. Identificar el branch aplicable:

**Branch 1 — `--from <doc>` provisto**
- Leer el doc apuntado (resuelto desde la raíz del proyecto, salvo path absoluto) como contexto PRIMARIO.
- Si `docs/arquitectura/overview.md` también existe, leerlo como contexto SECUNDARIO.
- En el README del cambio, agregar sección "Alineación con arquitectura" notando coincidencias o divergencias entre las dos fuentes.
- Si el doc apuntado por `--from` no existe, no es legible o está vacío → `status: blocked` con mensaje específico.

**Branch 2 — overview.md existe (sin `--from`)**
- Llamar `bootstrap.read_overview(root)` para obtener el contenido.
- Usar el overview como contexto PRIMARIO.
- Consultar CodeGraph como contexto SECUNDARIO si está disponible:
  - Tool de entrada: `mcp__codegraph__codegraph_explore` (exploración semántica del cambio descrito).
  - Para identificar entidades de dominio mencionadas: `mcp__codegraph__codegraph_search`.
  - Para entender dependencias entre módulos relevantes: `mcp__codegraph__codegraph_impact` + `mcp__codegraph__codegraph_status`.
- En el README, referenciar el overview como fuente arquitectónica.

**Branch 3a — sin overview pero hay código (`stacks != []`)**
- CodeGraph como contexto único.
- Invocar en este orden:
  1. `mcp__codegraph__codegraph_explore` — exploración semántica del cambio descrito.
  2. `mcp__codegraph__codegraph_search` — buscar símbolos por nombre si la descripción menciona entidades concretas.
  3. `mcp__codegraph__codegraph_impact` — blast radius del área potencialmente afectada.
  4. `mcp__codegraph__codegraph_status` — panorama general del índice si el contexto es desconocido.
- Comportamiento equivalente al `/fg-plan` clásico antes de C.1.

**Branch 3b — sin overview, sin código, y vision NO declinada**
- Condición: `read_overview(root) is None` AND `context.stacks == []` (o `pending_detection: true`) AND `context.vision_skipped == false`.
- Acción: abortar con `status: blocked`. Mensaje al dev:
  > "No hay contexto arquitectónico. Corré `/fg-setup` en modo bootstrap para inicializar la visión del sistema, después volvé a `/fg-plan`."

**Branch 3c — sin overview, sin código, vision SÍ declinada**
- Condición: lo mismo que 3b pero `context.vision_skipped == true`.
- Acción: proceder en modo degradado. El dev eligió no tener visión — respetarla.
- README incluye sección explícita: `Contexto: desconocido (visión declinada)`.
- Generar el README del cambio sin contexto arquitectónico; el `/fg-design` que sigue trabajará con lo que tenga.
- `status: success` con `warnings: [vision_skipped, degraded_context]`.

**IMPORTANTE**: el orden de check es estricto: primero `--from` (Branch 1), luego `overview.md` (Branch 2), luego stacks (Branch 3a vs 3b/3c según vision_skipped).

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
- Resolver contexto según prioridad: `--from` > `overview.md` > CodeGraph.
- Consultar CodeGraph usando los tool names reales: `mcp__codegraph__codegraph_explore` (entrada por defecto), `mcp__codegraph__codegraph_search`, `mcp__codegraph__codegraph_impact`, `mcp__codegraph__codegraph_status`. No usar narrativa vaga como "consultar CodeGraph" sin el nombre del tool.
- Preguntar sobre el problema cuando algo no quede claro.
- Escribir el `README.md` en español.
- Usar `YYYY-MM` (año-mes) en el nombre de la carpeta, NO `YYYY-MM-DD`.

### Preguntar

- Solo cuando la inferencia de tipo o nombre sea genuinamente ambigua.
- Solo cuando el alcance del problema tenga huecos importantes que afecten el diseño.

### Nunca

- Pedirle al dev que escriba el tipo o el nombre en kebab-case por su cuenta.
- Asumir alcance o restricciones que el dev no mencionó. Si no se sabe, preguntar.
- Crear `diseño.md` (eso lo crea `/fg-design`).
- Crear `tareas.md` en modo Completo (eso lo crea `/fg-design`); en modo Rápido `/fg-plan` sí lo crea desde `templates/tareas-lite.md`.
- Tocar código del proyecto.
- Imponer estilos de arquitectura o stack.
- Asumir contexto cuando `context.vision_skipped == false` y no hay overview ni stacks — abortar con `status: blocked` y redirigir a `/fg-setup`.
- Evaluar el nivel de ceremonia — eso es juicio del orquestador, que lo determina antes de invocar `/fg-plan`.

## Envelope de retorno

```yaml
status: success | partial | blocked | skipped
executive_summary: 1-2 oraciones de lo que se hizo
artifacts:
  - docs/auditoria/cambios/<YYYY-MM>-<tipo>-<nombre>/README.md
  # en modo Rápido (determinado por el orquestador), también:
  # - docs/auditoria/cambios/<YYYY-MM>-<tipo>-<nombre>/tareas.md
inferred:
  tipo: <tipo inferido>
  nombre: <nombre kebab-case inferido>
next_recommended: /fg-design   # modo Completo; en modo Rápido → /fg-implement
risks: None | <riesgos detectados durante la conversación>
skill_resolution: paths-injected | fallback-registry | fallback-path | none
```
