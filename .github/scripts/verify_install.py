"""Verifica que `forge install` haya depositado los assets esperados en ~/.claude/.

Lo usa el job smoke-install del CI: corre el forge install real (sin red) y este
script confirma, en cada SO, que el depósito y el registro del hook PII funcionaron.
Sale con código != 0 si falta algo, para romper el job.
"""

import sys
from pathlib import Path

claude = Path.home() / ".claude"
errors: list[str] = []

# Las 8 skills del workflow, cada una en su carpeta con SKILL.md.
expected_skills = [
    "fg-setup",
    "fg-explore",
    "fg-plan",
    "fg-design",
    "fg-implement",
    "fg-review",
    "fg-update-arch",
    "fg-update-registry",
]
for skill in expected_skills:
    path = claude / "skills" / skill / "SKILL.md"
    if not path.is_file():
        errors.append(f"falta skill: {path}")

# Referencias compartidas (forge-shared).
for shared in ["skill-resolver", "engram-protocol", "fg-phase-common"]:
    path = claude / "skills" / "forge-shared" / shared / "SKILL.md"
    if not path.is_file():
        errors.append(f"falta shared: {path}")

# Sub-agentes (muestra representativa).
for agent in ["code-reviewer", "security-reviewer", "legacy-impact-analyzer"]:
    path = claude / "agents" / f"{agent}.md"
    if not path.is_file():
        errors.append(f"falta agent: {path}")

# Los 8 comandos del workflow, depositados flat en ~/.claude/commands/.
expected_commands = [
    "fg-setup",
    "fg-explore",
    "fg-plan",
    "fg-design",
    "fg-implement",
    "fg-review",
    "fg-update-arch",
    "fg-update-registry",
]
for cmd in expected_commands:
    path = claude / "commands" / f"{cmd}.md"
    if not path.is_file():
        errors.append(f"falta command: {path}")

# Hook PII registrado en settings.json.
settings = claude / "settings.json"
if not settings.is_file():
    errors.append(f"falta settings.json: {settings}")
elif "forge.filters.hook_user_prompt" not in settings.read_text(encoding="utf-8"):
    errors.append("settings.json no contiene el hook PII (forge.filters.hook_user_prompt)")

# Hook de guardrails registrado en settings.json.
if settings.is_file() and "forge.guards.hook_pre_tool" not in settings.read_text(encoding="utf-8"):
    errors.append("settings.json no contiene el hook de guardrails (forge.guards.hook_pre_tool)")

# Doctrina global del orquestador instalada como ~/.claude/CLAUDE.md.
claude_md = claude / "CLAUDE.md"
if not claude_md.is_file():
    errors.append(f"falta CLAUDE.md global: {claude_md}")
elif "institucional de forge" not in claude_md.read_text(encoding="utf-8"):
    errors.append("~/.claude/CLAUDE.md no contiene la doctrina institucional de forge")

if errors:
    print("SMOKE FAIL — el depósito de forge install está incompleto:")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)

print("SMOKE OK: skills, commands, forge-shared, agents, hook PII, hook guardrails y CLAUDE.md global instalados.")
