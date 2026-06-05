---
description: Reconcilia docs/arquitectura/ con los cambios estructurales cerrados. Propone diff por archivo; el dev acepta cada propuesta individualmente.
---

If the native `fg-update-arch` sub-agent is available, delegate this command to it.
Otherwise, read the skill file at `~/.claude/skills/fg-update-arch/SKILL.md` FIRST, then follow its instructions exactly inline.

CONTEXT:
- Working directory: !`pwd`
- Current project: !`basename "$(pwd)"`
- Scope: $ARGUMENTS
- Artifact store mode: engram

TASK:
Mantener docs/arquitectura/ sincronizada con la realidad del código. Leer el estado actual (overview.md, stack.md, decisions/). Identificar cambios cerrados con structural: true en su frontmatter que no hayan sido consolidados (arch_synced: false). Consultar CodeGraph para reconciliar topología: módulos top-level nuevos, entidades de dominio nuevas, cambios en dependencias internas, cambios en módulos transversales. Proponer diff por archivo (overview.md, stack.md, ADR nuevo si aplica) — NO todo-o-nada. El dev acepta cada propuesta individualmente. Si $ARGUMENTS especifica un scope (ej: desde-fecha 2026-04-01 o cambio nombre-cambio), procesar solo ese scope.

ENGRAM PERSISTENCE (artifact store mode: engram):
La skill fg-update-arch maneja la persistencia según engram-protocol.md.
Al completar, la skill puede guardar señales forge/discovery/{slug} para acoplamientos o patrones no obvios detectados durante la reconciliación. Las actualizaciones aceptadas de docs/arquitectura/ viven en el filesystem y se versionan con git.
