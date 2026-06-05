---
description: Define el cómo del cambio activo. Consulta CodeGraph, produce diseño.md, tareas.md y decisiones.md. Emite Review Workload Forecast.
---

If the native `fg-design` sub-agent is available, delegate this command to it.
Otherwise, read the skill file at `~/.claude/skills/fg-design/SKILL.md` FIRST, then follow its instructions exactly inline.

CONTEXT:
- Working directory: !`pwd`
- Current project: !`basename "$(pwd)"`
- Artifact store mode: engram

TASK:
Convertir el README.md del cambio activo en un plan técnico ejecutable. Leer README.md del cambio, consultar CodeGraph para identificar archivos afectados reales, definir enfoque técnico, documentar arquitectura y contratos de interfaz. Generar docs/auditoria/cambios/{cambio}/diseño.md, tareas.md y decisiones.md. Emitir el Review Workload Forecast (si enforcement != off). Si el proyecto es legacy (bootstrap.is_legacy_project), invocar el sub-agente legacy-impact-analyzer antes de definir el enfoque.

ENGRAM PERSISTENCE (artifact store mode: engram):
La skill fg-design maneja la persistencia según engram-protocol.md.
Al completar, la skill actualiza la señal de estado del cambio activo en engram con topic forge/{cambio}/state (tipo: architecture) indicando fase: design. Las decisiones técnicas grandes se guardan como señales adicionales en forge/decision/{slug}. El contenido completo (diseño.md, tareas.md, decisiones.md) vive en el filesystem.
