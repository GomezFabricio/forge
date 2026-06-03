<!-- forge:orchestrator -->
# Forge — workflow latente de spec-driven development

Forge está SIEMPRE LATENTE. No se activa, no se desactiva.

## Forge Init Guard (silencioso)

Antes de cualquier skill forge (fg-plan, fg-design, fg-implement, fg-review, fg-update-arch):
1. Si NO existe `.forge/` en el cwd del proyecto → correr `/fg-setup` silenciosamente.
   El modo (bootstrap/adopt/upgrade) lo decide forge según el estado del directorio.
2. Continuar con la skill solicitada.

NO preguntes "¿activamos forge?". Si la tarea encaja, inicializá y ejecutá.

## Cuándo invocar forge

Invocar la cadena correspondiente cuando el dev expresa intent de:

| Intent | Cadena |
|---|---|
| Arrancar sistema/app nuevo desde cero | /fg-setup bootstrap → conversación visión → /fg-plan iterativo |
| Implementar PRD/spec documentado | /fg-setup bootstrap → ingesta doc → /fg-plan iterativo |
| Agregar feature a sistema existente | /fg-setup adopt si no está → /fg-plan |
| Refactor/modificar legacy | /fg-setup adopt + tag legacy → /fg-plan → /fg-design con impact analysis |

## Cuándo NO invocar forge

- Fix de typo, 1 línea, comment.
- Exploración / responder preguntas.
- Dev pide explícito "sin forge".
<!-- /forge:orchestrator -->
