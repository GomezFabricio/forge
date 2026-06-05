---
description: Valida y cierra el cambio activo. Corre la suite completa, valida TDD Cycle Evidence, invoca sub-agentes especialistas y escribe la sección Cierre del README.
---

If the native `fg-review` sub-agent is available, delegate this command to it.
Otherwise, read the skill file at `~/.claude/skills/fg-review/SKILL.md` FIRST, then follow its instructions exactly inline.

CONTEXT:
- Working directory: !`pwd`
- Current project: !`basename "$(pwd)"`
- Artifact store mode: engram

TASK:
Validar que la implementación es correcta y el TDD se aplicó realmente. Correr la suite completa de tests (rules.review.test_command del config). Si TDD está activo, cargar _shared/strict-tdd-verify.md y validar la TDD Cycle Evidence contra ejecución real. Invocar sub-agentes especialistas según el cambio (code-reviewer siempre; dba-reviewer/frontend-reviewer/security-reviewer/legacy-impact-analyzer según contexto). Detectar cambios estructurales con structural_detector.py. Escribir la sección Cierre del README.md y actualizar Estado a cerrado. Sugerir fg-update-arch si el cambio es estructural.

ENGRAM PERSISTENCE (artifact store mode: engram):
La skill fg-review maneja la persistencia según engram-protocol.md.
Al cerrar el cambio, la skill actualiza forge/{cambio}/state con fase: cerrado. Si detecta cambios estructurales, puede guardar una señal forge/decision/{slug} apuntando al ADR o la decisión técnica relevante. El reporte de review completo (sección Cierre) vive en docs/auditoria/cambios/{cambio}/README.md en el filesystem.
