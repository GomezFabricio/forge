"""forge.filters — filtro PII pre-Anthropic.

Submódulos:
- hook_user_prompt: entry point del hook UserPromptSubmit de Claude Code.
- analyzer: Presidio Analyzer con recognizers built-in + custom.
- anonymizer: Presidio Anonymizer con placeholders por tipo de entidad.
- recognizers: custom recognizers (AR + secretos técnicos).
- redaction_log: logging append-only a .forge/redactions.jsonl.

Public API:
"""

from forge.filters.analyzer import build_analyzer
from forge.filters.anonymizer import build_anonymizer
from forge.filters.hook_user_prompt import process_prompt

__all__ = ["process_prompt", "build_analyzer", "build_anonymizer"]
