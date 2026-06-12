---
name: fg-update-registry
description: Genera o regenera .atl/skill-registry.md como índice de skills del proyecto. Lee solo el frontmatter de cada SKILL.md para extraer nombre y path; no resume ni genera compact rules. Invocar después de fg-setup y cada vez que se instalen, creen, muevan o renombren skills.
when_to_apply: Invocada automáticamente por el orquestador después de /fg-setup (primera ejecución). También invocable manualmente cuando el dev instala, crea, mueve o renombra skills del proyecto.
---

> **ORCHESTRATOR GATE**: Si cargaste esta skill vía la tool `Skill`, sos el ORQUESTADOR — STOP.
> NO ejecutes estas instrucciones inline. Delegá al sub-agente `fg-update-registry` usando la primitiva
> de delegación de tu plataforma (ej. la tool `Task` o el sub-agente nativo). Esta skill es
> solo para EXECUTORS.

## Executor Override

Si SOS el sub-agente `fg-update-registry` (NO el orquestador), el gate de arriba NO aplica. Continuá con
el trabajo de la fase que sigue. NO delegues. NO llamés a la tool `Skill`. NO llamés a la tool
`Task`. Sos el executor — ejecutá.

> Cargar antes: `skills/_shared/fg-phase-common.md` (secciones A, B, E)

# /fg-update-registry

## Propósito

Mantener `.atl/skill-registry.md` actualizado como índice de skills disponibles para el proyecto. Sin este índice, el orquestador no puede resolver skills al lanzar sub-agentes — trabajan sin standards del proyecto.

El registry es un ÍNDICE, no un resumen. Solo contiene: nombre, trigger/descripción, scope y el path exacto al `SKILL.md`. Los sub-agentes reciben esos paths y leen los archivos completos — autor intent preservado, sin digestión ni compact rules.

## Cuándo aplicarla

- **Automáticamente después de `/fg-setup`**: el orquestador invoca `/fg-update-registry` una vez que el setup está completo.
- **Manualmente** cuando el dev instala, crea, mueve o renombra skills del proyecto.
- **Después de `forge install`**: para indexar skills que vengan del update del framework.

## Proceso

### 1. Escanear fuentes en orden

Escanear en este orden y registrar qué se encontró:

**(a) Skills del proyecto** — en el directorio raíz del repo:
- Patrón `skills/*/SKILL.md` (skills con carpeta propia)
- Patrón `skills/*.md` (skills flat, sin subcarpeta)

**(b) Skills del usuario** — en el directorio global:
- Patrón `~/.claude/skills/*/SKILL.md`

Registrar ambas fuentes en el campo `sources_scanned` del resultado.

**(c) Path adicional del argumento** — si el orquestador pasó un path adicional como argumento (`$ARGUMENTS`), sumarlo como fuente extra de escaneo con el mismo tratamiento que las demás fuentes: buscar `*/SKILL.md` y `*.md` dentro de ese path, aplicar los mismos filtros y deduplicación.

### 2. Filtrar skills excluidas

NUNCA incluir en el registry:
- Skills con prefijo `fg-` (las del workflow de forge).
- Skills con prefijo `sdd-` (las del harness SDD).
- Carpetas `_shared` y `forge-shared` (módulos compartidos, no invocables).
- La propia skill `skill-registry` (el índice no se indexa a sí mismo).

### 3. Leer solo el frontmatter

Para cada skill encontrada, leer el bloque YAML entre los delimitadores `---` al inicio del archivo. Extraer:
- `name`: nombre de la skill (identificador).
- `description`: texto de trigger/descripción para matchear en el Paso 2 del skill-resolver.

No parsear el cuerpo de la skill. Formatos heterogéneos están bien por diseño — el frontmatter es suficiente.

**Reglas de inclusión/exclusión por frontmatter**:

- Archivos **sin bloque frontmatter** delimitado por `---` → SALTAR silenciosamente (no indexar). Esto excluye automáticamente `README.md`, `CHANGELOG.md` y cualquier archivo Markdown sin frontmatter que pueda existir en `skills/`.
- Archivos con frontmatter pero **sin `name`** → usar el stem del archivo como nombre.
- Archivos con frontmatter pero **sin `description`** → SALTAR (una entrada sin texto de trigger no sirve para matching); listar el archivo en el envelope como `skipped` con motivo `missing_description`.
- Archivos con frontmatter, `name` y `description` presentes → indexar normalmente.

### 4. Deduplicar por nombre

Si la misma skill aparece en múltiples fuentes:
- **Project beats user**: una skill del proyecto tiene prioridad sobre la del usuario global.
- **Múltiples ubicaciones globales**: gana la primera en orden de escaneo.

### 5. Generar `.atl/skill-registry.md`

> **Excepción explícita a E.1**: el registry es un artefacto REGENERABLE — sobrescribir es la semántica correcta. Cada ejecución de `/fg-update-registry` reemplaza el archivo anterior con el estado actual. No preguntar al dev ni preservar el anterior.

**5a. Asegurar que el directorio existe**: antes de escribir el archivo, verificar si `.atl/` existe. Si no existe, crearlo con Bash (`mkdir -p .atl`). Este directorio puede estar ausente en proyectos donde `/fg-setup` nunca corrió.

Escribir el archivo con esta estructura:

```markdown
# Skill Registry — {nombre del proyecto}

<!-- Auto-generado por forge (/fg-update-registry). Regenerar tras instalar, crear, mover o renombrar skills. -->

Última actualización: {YYYY-MM-DD}

## Fuentes escaneadas

- skills/ (proyecto)
- ~/.claude/skills (usuario)

## Contrato

**Solo para delegadores.** Este registry es un índice, no un resumen. Cualquier agente que lance sub-agentes lo lee para seleccionar skills relevantes, luego pasa los paths exactos de `SKILL.md` para que el sub-agente los lea antes de trabajar.

`SKILL.md` es la fuente de verdad. No inyectar resúmenes generados ni compact rules; pasar paths para que los sub-agentes carguen el contrato completo del autor.

## Skills

| Skill | Trigger / descripción | Scope | Path |
| --- | --- | --- | --- |
| `{name}` | {description} | project | `{path}` |
| `{name}` | {description} | user | `{path}` |

## Protocolo de carga

1. Matchear contexto de tarea y archivos destino contra la columna `Trigger / descripción`.
2. Pasar solo los valores `Path` coincidentes al sub-agente bajo `## Skills to load before work`.
3. Indicar al sub-agente que lea esos archivos `SKILL.md` ANTES de leer, escribir, revisar, testear o crear artefactos.
4. Si ninguna skill coincide, continuar sin inyección y reportar el campo `skill_resolution` con valor `none`.
```

Si no hay skills (tabla vacía), escribir el archivo igual con la tabla sin filas — los agentes dejan de buscar.

### 6. Persistir en engram

Llamar `mem_save` con:
- `title: skill-registry`
- `topic_key: skill-registry`
- `type: config`
- `scope: project`
- `capture_prompt: false`
- `content`: resumen indicando cuántas skills se indexaron y la fecha.

### 7. Reportar al dev

```
Skill registry actualizado en .atl/skill-registry.md
{N} skills indexadas: {lista de nombres}
Fuentes escaneadas: {lista}
Engram: actualizado
```

## Reglas

### Siempre

- Sobrescribir `.atl/skill-registry.md` siempre (es un artefacto regenerable — excepción explícita a fg-phase-common E.1).
- Leer solo el frontmatter de cada skill. No parsear el cuerpo.
- Project beats user en deduplicación.
- Escribir el registry aunque no haya skills (tabla vacía).
- Guardar en engram con `capture_prompt: false`.

### Nunca

- Generar compact rules, resúmenes, ni ningún texto derivado del cuerpo de la skill.
- Indexar skills `fg-*`, `sdd-*`, `_shared`, `forge-shared` o `skill-registry`.
- Inventar skills que no existan en el filesystem.

## Guía de autoría

Las skills que indexa este registry DEBERÍAN declarar reglas verificables (regla + ejemplo correcto/incorrecto + cómo verificar) para que los revisores puedan validar contra contratos chequeables. El sub-agente lee esas reglas en el propio archivo SKILL.md; el registry nunca las resume.

## Envelope de retorno

```yaml
status: success | partial | blocked
executive_summary: 1-2 oraciones de lo que se indexó
registry_path: .atl/skill-registry.md
skills_indexed: <N>
sources_scanned:
  - skills/ (proyecto)
  - ~/.claude/skills (usuario)
engram_updated: true | false
artifacts:
  - .atl/skill-registry.md (regenerado)
next_recommended: none
risks: None | <descripción de riesgos detectados>
skill_resolution: paths-injected | fallback-registry | fallback-path | none
```
