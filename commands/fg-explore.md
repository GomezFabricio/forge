---
description: Produce el mapa del cambio activo consultando CodeGraph. Genera exploracion.md reutilizable por fg-design. Fase 0 independiente — puede correr antes de fg-plan.
---

If the native `fg-explore` sub-agent is available, delegate this command to it.
Otherwise, read the skill file at `~/.claude/skills/fg-explore/SKILL.md` FIRST, then follow its instructions exactly inline.

CONTEXT:
- Working directory: !`pwd`
- Current project: !`basename "$(pwd)"`
- Change / area to explore: $ARGUMENTS
- Artifact store mode: engram

TASK:
Mapear el cambio activo consultando los MCP tools de CodeGraph en pasada ordenada (codegraph_explore → codegraph_search → codegraph_files → codegraph_node → codegraph_callers → codegraph_callees → codegraph_impact → codegraph_status). Generar docs/auditoria/cambios/{cambio}/exploracion.md con: área del cambio, archivos afectados reales, consumidores/blast radius, acoplamientos no obvios, señales fuertes (consumidores, blast_radius, toca_transversales, nivel_sugerido) y resumen de riesgo. Fase 0 independiente: no requiere que fg-plan haya corrido previamente.

ENGRAM PERSISTENCE (artifact store mode: engram):
La skill fg-explore maneja la persistencia según engram-protocol.md.
Al completar, la skill actualiza la señal de estado del cambio activo en engram con topic forge/{cambio}/state (tipo: architecture) indicando fase: explore y la ruta del mapa generado. El contenido del mapa vive en docs/auditoria/cambios/{cambio}/exploracion.md en el filesystem.
