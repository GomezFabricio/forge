"""Hook UserPromptSubmit del filtro PII pre-Anthropic.

`process_prompt` recibe el input parseado del hook (dict con `prompt`,
`session_id`, `transcript_path`, `cwd`, `hook_event_name`) y devuelve un
dict que Claude Code interpreta:

- `{}` → no hay decisión, pasa el prompt sin modificar.
- `{"decision": "block", "reason": "..."}` → bloquea con mensaje al dev.
- `{"continue": true, "modified_prompt": "..."}` → reemplaza el prompt.

En esta fase inicial el processor es pass-through: siempre devuelve `{}`.
Los commits siguientes agregan recognizers, redacción con placeholders y el
override `#fg-pass`.
"""


def process_prompt(input_data: dict) -> dict:
    return {}
