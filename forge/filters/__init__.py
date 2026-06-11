"""forge.filters — filtro PII pre-Anthropic.

Submódulos:
- hook_user_prompt: entry point del hook UserPromptSubmit de Claude Code.
- analyzer: Presidio Analyzer con recognizers built-in + custom.
- anonymizer: Presidio Anonymizer con placeholders por tipo de entidad.
- recognizers: custom recognizers (AR + secretos técnicos).
- redaction_log: logging append-only a .forge/auditoria-pii.jsonl.

Public API (lazy imports — presidio is optional and expensive to import eagerly):
"""

__all__ = ["process_prompt", "build_analyzer", "build_anonymizer"]


def __getattr__(name: str):
    if name == "process_prompt":
        from forge.filters.hook_user_prompt import process_prompt

        return process_prompt
    if name == "build_analyzer":
        from forge.filters.analyzer import build_analyzer

        return build_analyzer
    if name == "build_anonymizer":
        from forge.filters.anonymizer import build_anonymizer

        return build_anonymizer
    raise AttributeError(f"module 'forge.filters' has no attribute {name!r}")


def __dir__() -> list:
    return sorted(set(globals()) | set(__all__))
