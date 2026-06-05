---
description: Convierte una descripción en lenguaje natural en una carpeta de cambio con README.md inicial. Infiere tipo y nombre kebab-case automáticamente.
---

If the native `fg-plan` sub-agent is available, delegate this command to it.
Otherwise, read the skill file at `~/.claude/skills/fg-plan/SKILL.md` FIRST, then follow its instructions exactly inline.

CONTEXT:
- Working directory: !`pwd`
- Current project: !`basename "$(pwd)"`
- Change description: $ARGUMENTS
- Artifact store mode: engram

TASK:
Convertir la descripción libre del dev en una carpeta de cambio bien estructurada. Inferir el tipo (feat/fix/refactor/chore/docs/perf/test) y el nombre en kebab-case desde el lenguaje natural. Resolver contexto arquitectónico por prioridad: --from <doc> > docs/arquitectura/overview.md > CodeGraph. Generar docs/auditoria/cambios/YYYY-MM-tipo-nombre/README.md inicial con qué, por qué, alcance y restricciones. En modo Rápido (determinado por el orquestador antes de invocar), generar también tareas.md desde templates/tareas-lite.md.

ENGRAM PERSISTENCE (artifact store mode: engram):
La skill fg-plan maneja la persistencia según engram-protocol.md.
Al completar, la skill actualiza la señal de estado del cambio activo en engram con topic forge/{cambio}/state (tipo: architecture) indicando fase: plan y la ruta del README.md creado. El contenido del README vive en docs/auditoria/cambios/{cambio}/README.md en el filesystem.
