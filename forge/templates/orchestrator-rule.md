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

## Gradación proporcional del intent

Cuando forge entra, no siempre necesita el ritual completo. El portero proporcional
clasifica cada cambio en uno de tres niveles de ceremonia y propone el nivel al dev
antes de arrancar. El intent ya existe (forge es latente) — el portero solo gradúa
cuánto expediente aplica.

### Los 3 niveles

| Nivel | Qué saltea | Cuándo aplica |
|-------|------------|---------------|
| **Libre** | forge no entra. Sin carpeta, sin ciclo. | Typo, 1 línea, pregunta, "sin forge" explícito. |
| **Rápido** | Saltea solo `/fg-design`. Corre `/fg-plan` → `/fg-implement` → `/fg-review`. | Cambio chico, tipo ligero (docs/chore/fix), sin palabras de escala, arquitectura al día. |
| **Completo** | Ritual completo sin cambios: plan → design → implement → review. | Feat, refactor, palabras de escala, ambigüedad, arquitectura desactualizada. |

### Piso innegociable

`/fg-review` SIEMPRE corre. No es configurable. No se salta. En modo Rápido, Completo
o cualquier variante futura: `/fg-review` ejecuta incondicionalmente al final del ciclo.
Esta garantía no la controla el dev, no la controla la config, no la controla el portero.

### Condición habilitante de Rápido: arquitectura al día

Rápido solo está disponible si `docs/arquitectura/` está al día. El portero lo verifica
leyendo el frontmatter de `docs/auditoria/cambios/*/README.md`: si existe algún cambio
con `structural: true` y sin `arch_synced: true`, la arquitectura está desactualizada
y el portero fuerza Completo, informando al dev cuántos cambios estructurales están
pendientes de sincronizar.

Limitación declarada: este detector solo ve cambios que pasaron por forge y fueron
marcados `structural`. Cambios manuales externos no se detectan. Es una señal de piso,
no de techo: "desactualizada" es confiable; "al día" significa "al día hasta donde forge sabe".
Si el dev elige ignorar un drift externo, `/fg-review` (piso innegociable) sigue cubriendo.

### Regla conservadora: ante la duda sin CodeGraph → Completo

Sin CodeGraph disponible, el portero no puede estimar impacto estructural con datos reales.
Ante señales ambiguas o contradictorias, la propuesta default es siempre Completo.
El dev puede declinar y elegir Rápido explícitamente (`--rapido`), pero el portero
no asume que un cambio es chico si no puede probarlo.

### Config de proyecto: `ceremonial_threshold`

`docs/auditoria/config.yaml` → `rules.workflow.ceremonial_threshold`:
- `auto` (default): el portero propone el nivel según señales y espera confirmación del dev.
- `lite`: sesga hacia Rápido siempre que se pueda; respeta la condición de arquitectura al día.
- `full`: fuerza Completo siempre, sin proponer ni preguntar. Para entornos de auditoría estricta.
<!-- /forge:orchestrator -->
