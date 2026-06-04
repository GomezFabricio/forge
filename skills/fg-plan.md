---
name: fg-plan
description: Entiende un cambio nuevo. El dev describe lo que quiere hacer en lenguaje natural y la skill infiere tipo, nombre kebab-case, contexto del codebase y genera el README inicial del cambio.
when_to_apply: El dev invoca /fg-plan con una descripción libre en lenguaje natural. Es el primer paso del workflow de cualquier cambio nuevo.
---

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

### 0. Resolver el modo de ejecución del ciclo

Al arrancar un ciclo nuevo, decidir si la sesión actual usa modo **interactivo** o **automático**:

- **Interactivo**: cada fase (`/fg-plan`, `/fg-design`, `/fg-implement`, `/fg-review`) pausa al cerrar y pregunta al dev si seguir o ajustar. Útil cuando se quiere supervisar paso a paso.
- **Automático**: las fases se encadenan sin pausa hasta el final del ciclo. Útil cuando el dev confía en el flow y quiere velocidad.

**Cache de sesión**: el orquestador cachea la respuesta para la sesión actual. Si ya hay un modo definido en esta sesión, **usar el cacheado sin volver a preguntar**. Si es la primera vez que se arranca un ciclo en la sesión, preguntar y cachear.

**Default sugerido desde config**: leer `rules.workflow.cycle_mode` de `docs/auditoria/config.yaml`. Si existe, usar ese valor como respuesta pre-seleccionada en la pregunta (no como respuesta automática — siempre preguntar la primera vez por sesión para que el dev pueda cambiar si quiere). Si no existe el config, el default es `interactive`.

Pregunta al dev (solo si no hay cache):

> "¿Modo del ciclo: interactivo o automático? (cacheado para la sesión actual; default del proyecto: {cycle_mode del config})"

El cache vive solo en el contexto del orquestador — no se persiste en filesystem ni engram. Sesión nueva → vuelve a preguntar.

### 0.5. Portero proporcional — decidir el nivel de ceremonia

Antes de inferir el tipo (paso 1), el portero evalúa qué nivel de ritual aplicar al cambio.
Este paso vive entre el modo de ciclo (paso 0) y la inferencia del tipo (paso 1) porque
necesita la descripción del dev y el contexto del proyecto, pero no el tipo final.

#### a) Leer las señales

1. **`ceremonial_threshold`** — leer `rules.workflow.ceremonial_threshold` de `docs/auditoria/config.yaml`.
   Si no existe el campo o el archivo, asumir `auto`.
2. **opt-in del dev** — el orquestador interpreta el intent natural del pedido y
   lo traduce a la señal de opt-in que recibe el portero. El lenguaje natural
   es el camino principal; las banderas son la forma explícita/manual del mismo mecanismo.

   Ejemplos de interpretación desde lenguaje natural:
   - "esto es delicado, hacelo completo" / "quiero el ciclo completo" → `opt_in = "completo"`
   - "es un toque rápido" / "algo simple, sin mucho proceso" → `opt_in = "rapido"`
   - "sin forge" / "no quiero el ciclo" → `opt_in = "libre"`
   - Sin señal de nivel en el pedido → `opt_in = None`

   Banderas explícitas (equivalentes, mayor precedencia que la interpretación):
   - `--rapido` o `--lite` → `opt_in = "rapido"`
   - `--completo` o `--full` → `opt_in = "completo"`
   - `--libre` o `--sin-forge` → `opt_in = "libre"`
3. **tipo inferido (lectura rápida)** — hacer una lectura preliminar y barata del tipo
   usando las heurísticas del paso 1 (docs/chore/test/style → ligero; feat/refactor → pesado).
   Esta lectura es provisional; el paso 1 sigue siendo la fuente de verdad del tipo final.
4. **palabras de escala** — buscar en la descripción del dev: "migrar", "reemplazar",
   "rediseñar", "reescribir", "módulo de", "todo el", "sistema de".
5. **arquitectura al día** — llamar a `check_arch_freshness(cambios_dir, arch_overview)` donde:
   - `cambios_dir = docs/auditoria/cambios/`
   - `arch_overview = docs/arquitectura/overview.md`

   > **Contrato de `check_arch_freshness`** (módulo: `forge/arch_freshness.py`):
   > - **Recibe**: `cambios_dir: Path`, `arch_overview: Path`
   > - **Retorna**: `dict` con claves `al_dia: bool`, `pendientes: int`, `sin_overview: bool`
   > - `al_dia` es `True` cuando `pendientes == 0` y `overview.md` existe.
   > - Detecta solo cambios que pasaron por forge y fueron marcados `structural: true` — limitación declarada.

#### b) Decidir el nivel

Llamar a `decidir_nivel(señales)` con las 5 señales del paso anterior.
La función aplica la precedencia: threshold > opt-in > tipo > palabras_de_escala.
Ambigüedad sin CodeGraph → Completo (regla conservadora).

   > **Contrato de `decidir_nivel`** (módulo: `forge/portero_decision.py`):
   > - **Recibe**: `senales: dict` con claves `threshold` (str), `opt_in` (str|None), `tipo_inferido` (str), `palabras_de_escala` (list[str]), `arquitectura_al_dia` (bool)
   > - **Retorna**: `dict` con claves `nivel_propuesto` (str: `"libre"` | `"rapido"` | `"completo"`), `razon` (str), `confianza` (str: `"alta"` | `"media"` | `"baja"`)
   > - Función pura: sin I/O, sin lectura de filesystem.

#### c) UX propone-y-confirma

El portero NUNCA aplica el nivel solo — siempre lo propone al dev primero.

**Excepción — threshold=full**: avisar en una línea y seguir sin preguntar.
> "ceremonial_threshold=full: modo Completo forzado por configuración del proyecto."

**Para cualquier otro nivel propuesto**:

> "Esto parece un cambio {chico/mediano/grande}. Propongo modo **{Rápido/Completo/Libre}**
> ({razón breve, ej: 'tipo docs, descripción acotada, arquitectura al día'}).
> ¿Seguimos en {nivel} o preferís {alternativa}? [Enter = aceptar / rapido / completo / libre]"

**Interacción con `cycle_mode`**:
- **Interactivo**: siempre mostrar la propuesta y esperar confirmación del dev.
- **Automático**: auto-confirmar la propuesta de la función, salvo que exista conflicto
  entre lo que el dev pidió y lo que la regla conservadora fuerza (ej: dev pide `--rapido`
  pero arquitectura desactualizada → Completo). En ese caso, aplicar el nivel conservador
  y reportarlo en el envelope sin bloquear el ciclo.

**Si el dev propone Libre**: forge NO crea la carpeta de cambio ni sigue con el ciclo.
Reportar `status: skipped` y explicar que el portero clasificó el cambio como Libre.

#### d) Cachear y reportar

Guardar el nivel resuelto como `ceremony_level` en el contexto de la sesión (igual que
`cycle_mode`). Reportarlo en el envelope de `/fg-plan` bajo la clave `ceremony_level`.

Si el nivel es **Rápido**: después del paso 4 (crear carpeta), generar `tareas.md` directamente
desde `templates/tareas-lite.md` en lugar de dejar que `/fg-design` lo genere. NO crear
`diseño.md`. Continuar con paso 5 y siguientes como de costumbre.

Si el nivel es **Completo**: flujo estándar sin cambios.

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
- Consultar CodeGraph como contexto SECUNDARIO si está disponible.
- En el README, referenciar el overview como fuente arquitectónica.

**Branch 3a — sin overview pero hay código (`stacks != []`)**
- CodeGraph como contexto único.
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

- Resolver el modo de ejecución del ciclo en el paso 0 — preguntar solo si no hay cache de sesión.
- Inferir tipo y nombre del lenguaje natural del dev.
- Resolver contexto según prioridad: `--from` > `overview.md` > CodeGraph.
- Preguntar sobre el problema cuando algo no quede claro.
- Escribir el `README.md` en español.
- Usar `YYYY-MM` (año-mes) en el nombre de la carpeta, NO `YYYY-MM-DD`.

### Preguntar

- El modo de ejecución del ciclo (interactivo/automático) — solo si no hay cache de sesión.
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

## Envelope de retorno

```yaml
status: success | partial | blocked | skipped
executive_summary: 1-2 oraciones de lo que se hizo
cycle_mode: interactivo | automatico
ceremony_level: libre | rapido | completo   # resuelto por el portero en paso 0.5
artifacts:
  - docs/auditoria/cambios/<YYYY-MM>-<tipo>-<nombre>/README.md
  # en modo Rápido, también:
  # - docs/auditoria/cambios/<YYYY-MM>-<tipo>-<nombre>/tareas.md
inferred:
  tipo: <tipo inferido>
  nombre: <nombre kebab-case inferido>
next_recommended: /fg-design   # modo Completo; en modo Rápido → /fg-implement
risks: None | <riesgos detectados durante la conversación>
```
