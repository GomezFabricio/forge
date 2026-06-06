---
description: Adopta forge en el proyecto activo. Detecta stack, genera docs/auditoria/config.yaml y skill-registry. No crea CLAUDE.md (la doctrina del orquestador es global). Idempotente.
---

If the native `fg-setup` sub-agent is available, delegate this command to it.
Otherwise, read the skill file at `~/.claude/skills/fg-setup/SKILL.md` FIRST, then follow its instructions exactly inline.

CONTEXT:
- Working directory: !`pwd`
- Current project: !`basename "$(pwd)"`
- Project root override: $ARGUMENTS
- Artifact store mode: engram

TASK:
Adoptar forge en el proyecto activo. Detectar el stack (pyproject.toml, package.json, go.mod, etc.), generar docs/auditoria/config.yaml con defaults conservadores, indexar el código con CodeGraph y generar .atl/skill-registry.md. NO crear CLAUDE.md: la doctrina del orquestador es global (`~/.claude/CLAUDE.md`, vía `forge install`). Si el directorio no tiene manifiestos conocidos, operar en modo bootstrap (crear config con pending_detection: true). Idempotente: re-ejecutar solo agrega lo faltante.

ENGRAM PERSISTENCE (artifact store mode: engram):
La skill fg-setup maneja la persistencia según engram-protocol.md.
Al completar, la skill guarda una señal en engram con topic forge/setup/{project} (tipo: config) con el stack detectado, test runner, modo de operación y paths de archivos creados. El contenido completo vive en docs/auditoria/config.yaml en el filesystem del proyecto.
