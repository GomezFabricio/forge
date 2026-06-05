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

- Confirmar qué archivos cambiados (provistos por git) tocan módulos top-level reales con símbolos, consultando el índice actual de CodeGraph (`codegraph files`). CodeGraph no compara revisiones: el eje temporal lo aporta git vía la lista de archivos cambiados; CodeGraph solo valida la realidad estructural del estado actual.
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

## Dos vías de integración

CodeGraph se integra de dos maneras distintas, que **no deben mezclarse**:

| Vía | Quién la usa | Cómo | Cuándo |
|-----|--------------|------|--------|
| **CLI (subprocess)** | Código Python (`structural_detector.py`) | `subprocess.run(["codegraph", ...])` | Análisis determinístico, fuera de un agente LLM |
| **MCP tools** | Skills y agentes (LLM en runtime) | `mcp__codegraph__codegraph_*` | Durante `/fg-plan`, `/fg-design`, etc., cuando un modelo invoca tools |

El código Python no puede invocar MCP tools; las skills no deben invocar subprocess. Mantener esta separación es lo que hace que cada integración sea predecible y testeable.

## Estructura de queries típicas

Referencia de versión: CodeGraph v0.9.9.

| Query lógica | Vía MCP (skills/LLM) | Vía CLI (código Python) |
|---|---|---|
| ¿Qué llama a un símbolo? | `mcp__codegraph__codegraph_callers` | `codegraph callers <sym> -j` |
| ¿A qué llama un símbolo? | `mcp__codegraph__codegraph_callees` | `codegraph callees <sym> -j` |
| Blast radius / impacto transitivo | `mcp__codegraph__codegraph_impact` | `codegraph impact <sym> -d N -j` |
| Buscar símbolos por nombre o tipo | `mcp__codegraph__codegraph_search` | `codegraph query <s> -k kind -j` |
| Estructura de archivos y módulos | `mcp__codegraph__codegraph_files` | `codegraph files --format grouped -j` |
| Estadísticas del índice | `mcp__codegraph__codegraph_status` | `codegraph status -j` |
| Tests afectados por archivos fuente | (n/a directo vía MCP) | `codegraph affected <files> -j` |
| Exploración semántica (orientada a LLM) | `mcp__codegraph__codegraph_explore` | (n/a — solo para agentes LLM) |
| Detalle de un símbolo concreto | `mcp__codegraph__codegraph_node` | (ver `codegraph query` con flags) |

> **Nota sobre diff de topología**: no existe un tool nativo para comparar revisiones.
> CodeGraph opera siempre sobre el índice actual (`.codegraph/codegraph.db`).
> El "diff de topología" entre dos commits es **derivado**: git aporta qué archivos
> cambiaron (`changed_files`), y `mcp__codegraph__codegraph_files` / `codegraph files`
> confirma qué módulos tienen símbolos reales en el estado actual del índice.
> Esto es lo que implementa `detect_top_level_module_changes()` en `forge/structural_detector.py`.
> No referenciar un tool inexistente como `codegraph__diff` o similar.

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
