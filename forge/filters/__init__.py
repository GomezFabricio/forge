"""forge.filters — filtro PII pre-Anthropic.

Submódulos:
- hook_user_prompt: entry point del hook UserPromptSubmit de Claude Code.
- analyzer: Presidio Analyzer con recognizers built-in + custom.
- anonymizer: Presidio Anonymizer con placeholders por tipo de entidad.
- recognizers: custom recognizers (AR + secretos técnicos).
"""
