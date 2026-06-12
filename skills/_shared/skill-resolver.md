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

El registry es un índice: nombre, trigger/descripción, scope y path exacto a cada `SKILL.md`. Esto es lo que consultás — los sub-agentes reciben paths y leen los archivos completos.

Orden de resolución:
1. ¿Ya está cacheado de antes en esta sesión? → usar cache.
2. `mem_search(query: "skill-registry", project: "{project}")` → `mem_get_observation(id)` para contenido completo.
3. Fallback: leer `.atl/skill-registry.md` desde la raíz del proyecto si existe.
4. ¿No se encontró registry? → proceder sin skills (pero avisar al dev: "No se encontró skill registry — los sub-agentes van a trabajar sin standards del proyecto. Correr `/fg-setup` seguido de `/fg-update-registry` para arreglar esto.").

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

Usar el campo `Trigger` en la tabla Skills del registry para matchear. Las skills cuyos triggers mencionan la tecnología o tipo de archivo relevante son matches.

**B. Contexto de tarea** — ¿qué ACCIONES va a hacer el sub-agente?

| Acción del sub-agente | Matchear skills con triggers que mencionen... |
|----------------------|------------------------------------------------|
| Crear un PR | "PR", "pull request" |
| Escribir/revisar código | El framework/lenguaje específico |
| Crear tickets | "Jira", "epic", "task" |
| Escribir docs Notion | "Notion", "RFC", "PRD" |
| Escribir comentarios | "comment" |
| Correr tests | "test", "vitest", "pytest", "playwright" |

### Paso 3: Pasar paths al sub-agente

De la tabla Skills del registry, tomar los valores `Path` de las skills matcheadas y pasarlos al sub-agente bajo `## Skills to load before work`:

```
## Skills to load before work

- {path/a/SKILL.md}
- {path/b/SKILL.md}
```

Agregar la instrucción: **"Leer estos archivos ANTES de empezar cualquier tarea."**

Va ANTES de las instrucciones de tarea del sub-agente, así los standards se cargan antes de empezar a trabajar.

**Contrato del registry**: el registry es un índice — solo contiene nombre, trigger/descripción, scope y path. Los sub-agentes leen los archivos `SKILL.md` completos para obtener el contrato real del autor. No inyectar resúmenes generados — pasar paths para preservar el intent original.

### Paso 4: Incluir convenciones del proyecto

Si el registry tiene una sección **Fuentes escaneadas** o convenciones adicionales y el sub-agente va a trabajar en el código del proyecto, agregar también:

```
## Project Conventions
Leer estos archivos para patrones específicos del proyecto:
- {path1} — {notas}
- {path2} — {notas}
```

Las convenciones del proyecto son referencias cortas (paths + notas), así que pasarlas es barato. El sub-agente las lee solo si son relevantes para su tarea.

## Presupuesto de tokens

Pasar paths cuesta ~1 línea por skill. El sub-agente que lee 2-4 `SKILL.md` incurre el costo en SU contexto — ese es el punto: author intent completo, sin pérdida de información. Para una delegación típica que matchea 3-4 skills, el overhead de paths en el prompt del orquestador es despreciable.

Si matchean más de **5 skills**, mantener solo las 5 más relevantes (priorizar matches de contexto de código sobre matches de contexto de tarea).

## Compaction safety

Este protocolo es safe-de-compactación porque:
- El registry vive en engram/filesystem, no en la memoria del orquestador.
- Cada delegación re-lee el registry si hace falta (paso 1 maneja cache miss).
- Los paths se copian al prompt de cada sub-agente al momento del launch — aún si el orquestador se olvida, los sub-agentes reciben los paths y pueden leer los archivos.

## Feedback loop

Los sub-agentes DEBEN reportar el estado de resolución de skills en su envelope de retorno:

- `paths-injected` — recibieron paths bajo `## Skills to load before work` del orquestador (camino ideal).
- `fallback-registry` — no recibieron paths, self-loaded desde el skill registry.
- `fallback-path` — no recibieron paths, cargaron via path de `SKILL: Load`.
- `none` — no se cargaron skills en absoluto.

**Regla de auto-corrección del orquestador**: si un sub-agente reporta cualquier cosa que no sea `paths-injected`, el orquestador DEBE:
1. Re-leer el skill registry inmediatamente (pudo perderse por compactación).
2. Asegurar que TODAS las delegaciones subsiguientes incluyan `## Skills to load before work` con los paths correspondientes.
3. Loguear un warning al dev: "Skill cache miss detectado — registry recargado para futuras delegaciones."

Esto previene degradación silenciosa donde el orquestador se olvida de las skills después de la compactación y todos los sub-agentes posteriores trabajan sin standards.

## Guía de autoría

Las skills indexadas por el registry DEBERÍAN declarar reglas verificables (regla + ejemplo correcto/incorrecto + cómo verificar) para que los revisores puedan validar contra contratos chequeables. El sub-agente lee esas reglas en el propio `SKILL.md`; el registry nunca las resume.

## Puntos de integración con skills de forge

- **Orquestador de forge**: sigue este protocolo para TODAS las delegaciones a las 8 skills (`/fg-setup`, `/fg-explore`, `/fg-plan`, `/fg-design`, `/fg-implement`, `/fg-review`, `/fg-update-arch`, `/fg-update-registry`).
- **`/fg-review`**: única skill con permiso de delegar a roles especialistas. Cuando delega a `code-reviewer`, `security-reviewer`, etc., también sigue este protocolo.
- **Cualquier skill futura que delegue**: DEBE referenciar este protocolo.
