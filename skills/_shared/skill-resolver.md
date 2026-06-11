# Skill Resolver — protocolo de resolución de skills

> Cualquier agente que **delegue trabajo a sub-agentes** DEBE seguir este protocolo para resolver e inyectar skills relevantes.
> Aplica al orquestador de forge y a `/fg-review` (la única skill SDD que delega).

## Por qué existe

Los sub-agentes nacen SIN contexto sobre qué skills existen. Sin inyección de skills:
- Un sub-agente revisando un proyecto Next.js no conoce los patrones de React 19.
- Un sub-agente arreglando código no sigue las convenciones del proyecto.
- Un sub-agente creando un PR no usa el template del proyecto.

## Cuándo aplicar

Antes de CADA lanzamiento de sub-agente que involucre **leer, escribir o revisar código**. Saltar solo para delegaciones puramente mecánicas (ej: "corré este comando de test").

## Protocolo

### Paso 1: Obtener el Skill Registry (una vez por sesión)

El registry contiene una sección **Compact Rules** con reglas pre-digeridas por skill (5-15 líneas cada una). Esto es lo que inyectás — NO paths a archivos SKILL.md.

Orden de resolución:
1. ¿Ya está cacheado de antes en esta sesión? → usar cache.
2. `mem_search(query: "skill-registry", project: "{project}")` → `mem_get_observation(id)` para contenido completo.
3. Fallback: leer `.atl/skill-registry.md` desde la raíz del proyecto si existe.
4. ¿No se encontró registry? → proceder sin skills (pero avisar al dev: "No se encontró skill registry — los sub-agentes van a trabajar sin standards del proyecto. Correr `/fg-setup` o `/update-registry` para arreglar esto.").

### Paso 2: Matchear skills relevantes

Matchear skills en DOS dimensiones:

**A. Contexto de código** — ¿qué archivos va a tocar o revisar el sub-agente?

Mapear patrones de archivo a skills del registry (ejemplos comunes — siempre deferir al campo Trigger del registry como source of truth):
- `.tsx`, `.jsx` → skills de react.
- `.ts` → skills de typescript.
- `app/**`, `pages/**` → skills de framework (nextjs/angular/etc.).
- `.py` → skills de python/django.
- `.go` → skills de go.
- `*.test.*`, `*.spec.*` → skills de testing.
- Archivos de estilo → skills de tailwind/css.

Usar el campo `Trigger` en la tabla User Skills del registry para matchear. Las skills cuyos triggers mencionan la tecnología o tipo de archivo relevante son matches.

**B. Contexto de tarea** — ¿qué ACCIONES va a hacer el sub-agente?

| Acción del sub-agente | Matchear skills con triggers que mencionen... |
|----------------------|------------------------------------------------|
| Crear un PR | "PR", "pull request" |
| Escribir/revisar código | El framework/lenguaje específico |
| Crear tickets | "Jira", "epic", "task" |
| Escribir docs Notion | "Notion", "RFC", "PRD" |
| Escribir comentarios | "comment" |
| Correr tests | "test", "vitest", "pytest", "playwright" |

### Paso 3: Inyectar al prompt del sub-agente

De la sección **Compact Rules** del registry, copiar los bloques de las skills matcheadas directo al prompt del sub-agente:

```
## Project Standards (auto-resolved)

{pegar los bloques de compact rules para cada skill matcheada}
```

Va ANTES de las instrucciones de tarea del sub-agente, así los standards se cargan antes de empezar a trabajar.

**Regla clave**: inyectar el TEXTO de compact rules, NO paths. El sub-agente NO debe leer ningún SKILL.md — las reglas llegan pre-digeridas en su prompt.

### Paso 4: Incluir convenciones del proyecto

Si el registry tiene una sección **Project Conventions** y el sub-agente va a trabajar en el código del proyecto, agregar también:

```
## Project Conventions
Leer estos archivos para patrones específicos del proyecto:
- {path1} — {notas}
- {path2} — {notas}
```

Las convenciones del proyecto son referencias cortas (paths + notas), así que pasarlas es barato. El sub-agente las lee solo si son relevantes para su tarea.

## Presupuesto de tokens

La sección de compact rules debe agregar **50-150 tokens por skill** al prompt del sub-agente. Para una delegación típica que matchea 3-4 skills, eso es ~400-600 tokens — despreciable comparado al código que el sub-agente va a leer.

Si matchean más de **5 bloques** de skills, mantener solo los 5 más relevantes (priorizar matches de contexto de código sobre matches de contexto de tarea).

## Compaction safety

Este protocolo es safe-de-compactación porque:
- El registry vive en engram/filesystem, no en la memoria del orquestador.
- Cada delegación re-lee el registry si hace falta (paso 1 maneja cache miss).
- Las compact rules se copian al prompt de cada sub-agente al momento del launch — aún si el orquestador se olvida, los sub-agentes ya tienen las reglas.

## Feedback loop

Los sub-agentes DEBEN reportar el estado de resolución de skills en su envelope de retorno:

- `paths-injected` — recibieron `## Project Standards (auto-resolved)` del orquestador (camino ideal).
- `fallback-registry` — no recibieron standards, self-loaded desde el skill registry.
- `fallback-path` — no recibieron standards, cargaron via path de `SKILL: Load`.
- `none` — no se cargaron skills en absoluto.

**Regla de auto-corrección del orquestador**: si un sub-agente reporta cualquier cosa que no sea `paths-injected`, el orquestador DEBE:
1. Re-leer el skill registry inmediatamente (pudo perderse por compactación).
2. Asegurar que TODAS las delegaciones subsiguientes incluyan `## Project Standards (auto-resolved)`.
3. Loguear un warning al dev: "Skill cache miss detectado — registry recargado para futuras delegaciones."

Esto previene degradación silenciosa donde el orquestador se olvida de las skills después de la compactación y todos los sub-agentes posteriores trabajan sin standards.

## Puntos de integración con skills de forge

- **Orquestador de forge**: sigue este protocolo para TODAS las delegaciones a las 7 skills (`/fg-setup`, `/fg-explore`, `/fg-plan`, `/fg-design`, `/fg-implement`, `/fg-review`, `/fg-update-arch`).
- **`/fg-review`**: única skill con permiso de delegar a roles especialistas. Cuando delega a `code-reviewer`, `security-reviewer`, etc., también sigue este protocolo.
- **Cualquier skill futura que delegue**: DEBE referenciar este protocolo.
