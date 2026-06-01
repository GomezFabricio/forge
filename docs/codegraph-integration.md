# Integración con CodeGraph

CodeGraph (https://github.com/colbymchenry/codegraph) es la herramienta de análisis estructural del código usada por forge. Es MIT, 100% local, soporta 19 lenguajes, y reduce drásticamente las exploraciones a ciegas que tradicionalmente hacían las IAs con `Grep` y `Read` secuenciales.

Este documento describe cómo forge integra CodeGraph en su workflow.

## Cuándo se inicializa el índice

`/fg-setup` ejecuta la inicialización una sola vez al adoptar forge en el proyecto:

1. Verifica que el binario `codegraph` esté disponible en el PATH.
2. Indexa el código actual del proyecto en `.codegraph/codegraph.db`.
3. Agrega `.codegraph/` a `.gitignore` (el índice es local, no se versiona).
4. Reporta al dev la cantidad de nodos y aristas detectados.

Re-indexación incremental: el índice se actualiza automáticamente cuando se detectan cambios en archivos relevantes (manejado por un hook `PreToolUse` opcional o por invocación explícita desde las skills).

## Quién consulta CodeGraph y para qué

### `/fg-plan` — entender contexto del cambio

Cuando el dev describe lo que quiere hacer, `/fg-plan` consulta CodeGraph para responder:

- ¿Qué módulos del codebase están relacionados con la descripción?
- ¿Hay entidades de dominio existentes mencionadas en la descripción?
- ¿Hay dependencias entre módulos que el dev debería conocer al planificar?

Esto evita que `/fg-plan` invente contexto o haga grep textual ciego.

### `/fg-design` — identificar archivos afectados realmente

`/fg-design` consulta CodeGraph para responder:

- ¿Qué archivos contienen lógica relacionada con el cambio del `README.md`?
- ¿Hay clases, funciones o módulos que claramente se tocan?
- ¿Hay archivos que el cambio probablemente NO toca aunque parezcan relacionados por nombre?

La sección "Archivos afectados" de `diseño.md` se llena con esta información, no con suposiciones.

### `/fg-review` — detectar cambios estructurales

`/fg-review` invoca el detector estructural (`forge/structural_detector.py`) que consulta CodeGraph para:

- Identificar módulos top-level nuevos en HEAD vs HEAD~N (N = cambios del checklist).
- Detectar nuevas entidades de dominio (clases, structs, interfaces).
- Detectar cambios en aristas de dependencia entre módulos centrales.
- Detectar cambios en módulos marcados como transversales (config `modulos-transversales.yaml`).

Si alguna de estas señales aparece, `/fg-review` marca el cambio como `structural: true` en el frontmatter del `README.md`.

### `/fg-update-arch` — reconciliar topología vs documentación

`/fg-update-arch` consulta CodeGraph para:

- Listar los módulos top-level actuales del proyecto.
- Listar las dependencias internas entre módulos centrales.
- Identificar nuevas entidades de dominio que no están descriptas en `docs/arquitectura/overview.md`.

Cruza eso con la doc actual y propone diffs por archivo (overview.md, stack.md, ADRs nuevos).

### Roles especialistas — análisis profundo

- **`code-reviewer`**: consulta CodeGraph para entender el blast radius del cambio (qué otras partes del código dependen de lo modificado).
- **`legacy-impact-analyzer`**: consulta CodeGraph extensivamente para mapear dependencias ocultas. Es su herramienta principal de trabajo.
- **`dba-reviewer`**: consulta CodeGraph para identificar consumidores de las funciones de DB modificadas.

## Estructura de queries típicas

CodeGraph expone tools MCP que las skills invocan. Las queries más usadas:

| Query lógica | Tool MCP equivalente |
|---|---|
| ¿Qué llama a esta función? | `codegraph__callers_of(symbol)` |
| ¿Qué llama esta función? | `codegraph__callees_of(symbol)` |
| ¿Qué módulos top-level existen? | `codegraph__list_top_level_modules()` |
| ¿Qué módulos dependen del módulo X? | `codegraph__dependents_of(module)` |
| ¿Qué entidades hay en el módulo X? | `codegraph__symbols_in(module, filter: class|struct|interface)` |
| Diff de topología entre dos commits | `codegraph__diff(rev_a, rev_b)` |

Los nombres exactos de los tools dependen de la implementación específica de CodeGraph. `/fg-setup` valida que estos tools estén disponibles al instalar.

## Fallback a Explore / Read / Grep

CodeGraph cubre el 95% de los casos típicos. Para edge cases no cubiertos:

- **Búsqueda textual**: `Grep` directo.
- **Análisis semántico que CodeGraph no resuelve**: delegar al sub-agente `Explore` (general-purpose).

**Regla**: usar CodeGraph **siempre primero**. Si CodeGraph no puede responder la pregunta, recién entonces fallback a Grep/Read/Explore. Nunca arrancar con Grep cuando CodeGraph cubre el caso.

## Performance y costo

- **Indexación inicial**: depende del tamaño del codebase. Para proyectos típicos (< 100k LOC), tarda 30-90 segundos.
- **Query típica**: < 100ms. Determinístico, sin invocación de LLM.
- **Costo de tokens**: cero. CodeGraph corre 100% local.

Comparación con el approach "leer 20 archivos con Read para entender contexto":

| Approach | Tokens consumidos | Latencia | Determinismo |
|---|---|---|---|
| 20× Read + grep + interpretación LLM | ~50k-200k | varios segundos | bajo (varía por interpretación) |
| 1× CodeGraph query | 0 (local) | <100ms | alto (reproducible) |

Esta reducción es lo que vuelve viable correr `/fg-update-arch` seguido (semanal o cada N cambios) sin costo prohibitivo.

## Gitignore

`.codegraph/` está en `.gitignore` para evitar versionar el índice (que es regenerable y específico de cada máquina). Cada dev re-indexa con su propio `/fg-setup` al clonar el proyecto.

Si el equipo prefiere compartir el índice (proyectos muy grandes donde la indexación inicial es lenta), puede sacar `.codegraph/` del gitignore y commitearlo — pero hay que cuidar el merge cuando varios devs reindexan en paralelo. Por default, queda local.
