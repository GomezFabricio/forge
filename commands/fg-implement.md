---
description: Implementa las tareas del cambio activo con ciclo TDD (RED → GREEN → TRIANGULATE → REFACTOR). Genera TDD Cycle Evidence table.
---

If the native `fg-implement` sub-agent is available, delegate this command to it.
Otherwise, read the skill file at `~/.claude/skills/fg-implement/SKILL.md` FIRST, then follow its instructions exactly inline.

CONTEXT:
- Working directory: !`pwd`
- Current project: !`basename "$(pwd)"`
- Artifact store mode: engram

TASK:
Implementar las tareas del checklist en tareas.md del cambio activo, aplicando el ciclo TDD: SAFETY NET → UNDERSTAND → RED → GREEN → TRIANGULATE → REFACTOR. Si rules.implement.tdd es true en docs/auditoria/config.yaml, cargar _shared/strict-tdd.md y aplicar el ciclo estricto. Retomar desde la primera tarea no tachada si hay progreso previo. Al completar el batch, generar/mergear docs/auditoria/cambios/{cambio}/evidencia-tdd.md y reportar la TDD Cycle Evidence table. Respetar max_tasks_per_batch del config.

ENGRAM PERSISTENCE (artifact store mode: engram):
La skill fg-implement maneja la persistencia según engram-protocol.md.
Al completar o pausar un batch, la skill guarda progreso en engram con topic forge/{cambio}/implement-progress (tipo: architecture) para recuperación cross-session. Al finalizar todas las tareas, actualiza forge/{cambio}/state con fase: implement. El contenido de evidencia-tdd.md vive en el filesystem.
