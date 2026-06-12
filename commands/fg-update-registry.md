---
description: Genera o regenera el índice de skills del proyecto en .atl/skill-registry.md. Ejecutar después de instalar, crear, mover o renombrar skills.
---

If the native `fg-update-registry` sub-agent is available, delegate this command to it.
Otherwise, read the skill file at `~/.claude/skills/fg-update-registry/SKILL.md` FIRST, then follow its instructions exactly inline.

CONTEXT:
- Working directory: !`pwd`
- Current project: !`basename "$(pwd)"`
- Scope: $ARGUMENTS
- Artifact store mode: engram

TASK:
Generar o regenerar `.atl/skill-registry.md` como un índice de skills disponibles para el proyecto. Escanear las skills propias del proyecto (`skills/`) y las del usuario (`~/.claude/skills/`). Leer solo el frontmatter de cada SKILL.md para extraer nombre y descripción. Deduplicar por nombre (project beats user). Excluir `fg-*`, `_shared`, `forge-shared`, `sdd-*` y `skill-registry`. Escribir el registry con la tabla de skills (nombre, trigger/descripción, scope, path). Guardar en engram con `topic_key: skill-registry`. Si $ARGUMENTS especifica un scope o path adicional, incluirlo en el escaneo.

ENGRAM PERSISTENCE (artifact store mode: engram):
La skill fg-update-registry maneja la persistencia según engram-protocol.md.
Al completar, persiste el registry en engram con `topic_key: skill-registry` y `capture_prompt: false`.
