"""Tests del processor del hook UserPromptSubmit (forge.filters.hook_user_prompt)."""

from forge.filters.hook_user_prompt import process_prompt


class TestPassThrough:
    """En la fase inicial el processor deja pasar todo sin modificar.

    A medida que se agreguen recognizers y la lógica de redacción + override
    `#fg-pass`, estos tests evolucionan para validar el comportamiento real.
    El contrato actual: si el processor no tiene nada que decir, devuelve un
    dict vacío y Claude Code interpreta "no hay decisión, pasa el prompt".
    """

    def test_empty_prompt_returns_empty_decision(self):
        result = process_prompt({"prompt": ""})
        assert result == {}

    def test_prompt_without_known_patterns_returns_empty_decision(self):
        result = process_prompt({"prompt": "explicame este código"})
        assert result == {}
