---
name: fg-phase-common
description: Módulo compartido por todas las skills fg-*. Define el contrato de retorno, Review Workload Forecast, negociación de delivery strategy, reglas de idempotencia y carga de dependencias. Cargar las secciones aplicables antes de ejecutar cualquier skill fg-*.
---

# fg-phase-common — Módulo de lógica común

> **Cuándo cargar este módulo**: al inicio de cada skill `fg-*`, antes de ejecutar cualquier paso del proceso. Leer solo las secciones indicadas en el header de cada skill.

---

## Sección A — Carga de dependencias (Skill Loading)

### Cómo cada skill `fg-*` descubre y carga sus dependencias

Antes de ejecutar cualquier paso, cada skill debe:

1. **Leer `docs/auditoria/config.yaml`** del proyecto para conocer:
   - `rules.implement.tdd` → decide si cargar `_shared/strict-tdd.md`.
   - `rules.implement.test_command` → comando de test para `/fg-implement`.
   - `rules.review.test_command` y `rules.review.coverage_threshold` → para `/fg-review`.
   - `rules.pr_size.*` → para Review Workload Forecast (sección C).
   - `rules.workflow.cycle_mode` → default sugerido del ciclo; el orquestador lo pregunta una vez por sesión antes del primer ciclo.
   - `rules.implement.max_tasks_per_batch` → límite de tareas por batch para `/fg-implement`.

2. **GATE de re-detección lazy** (corre ANTES de cualquier aborto skill-específico):
   - Invocar `forge.bootstrap.needs_detection(root)`.
   - Si retorna `True`:
     - Invocar `forge.bootstrap.update_detection_fields(root)`.
     - Recargar `docs/auditoria/config.yaml` antes de continuar.
   - Si `pending_detection` queda en `true` después de la llamada (sin manifiestos detectados), reportar al dev claramente; NO abortar silenciosamente.
   - `needs_detection` ya maneja: config ausente → True; `pending_detection` ausente (config legacy) → True (EC-05); `last_detection` null → True; mtime de manifiesto posterior → True (EC-02).

3. **Cargar módulos condicionales**:
   - Si `rules.implement.tdd: true` → cargar `_shared/strict-tdd.md` (aplica en `/fg-implement`).
   - Si `rules.implement.tdd: true` y es `/fg-review` → cargar `_shared/strict-tdd-verify.md`.

4. **Fallback si `docs/auditoria/config.yaml` no existe**:
   - Asumir TDD desactivado (`tdd: false`).
   - Usar `context.test_runner.command` como comando de test.
   - Emitir advertencia al dev: "No se encontró `docs/auditoria/config.yaml`. Corré `/fg-setup` primero."

5. **Registrar en el envelope de retorno** el campo `skill_resolution` indicando qué módulos se cargaron.

---

## Sección B — Return Envelope (Contrato de retorno)

### Schema base (aplica a todas las skills `fg-*`)

Cada skill retorna un envelope YAML con al menos estos campos:

```yaml
status: success | partial | blocked
executive_summary: <1-2 oraciones de lo que se hizo o detectó>
artifacts:
  - <path1>         # archivos creados, modificados o leídos
  - <path2>
next_recommended: <siguiente skill o comando sugerido>
risks: None | <descripción de riesgos detectados>
skill_resolution: paths-injected | fallback-registry | fallback-path | none
```

> **Fuente canónica del enum `skill_resolution`**: los cuatro valores válidos (`paths-injected`, `fallback-registry`, `fallback-path`, `none`) están definidos aquí. Cualquier skill que liste el campo en su envelope DEBE usar exactamente estos valores.

### Campos específicos por skill (extensión del schema base)

Cada skill agrega campos propios **sin remover los base**:

| Skill | Campos adicionales |
|---|---|
| `/fg-plan` | `inferred.tipo`, `inferred.nombre` |
| `/fg-design` | `tasks_count`, `files_affected`, `decisiones_grandes`, `review_workload_forecast` |
| `/fg-implement` | `tdd_cycle_evidence`, `tests_summary`, `flags_for_review`, `batch_status` |
| `/fg-review` | `tdd_compliance`, `assertion_quality`, `coverage`, `roles_invoked`, `structural` |
| `/fg-setup` | `stack_detected`, `test_runner`, `audit_config`, `codegraph_indexed` |
| `/fg-update-arch` | `proposals_total`, `proposals_accepted`, `adrs_created` |
| `/fg-explore` | `mapa_path`, `senales_fuertes` (`consumidores`, `blast_radius`, `toca_transversales`, `nivel_sugerido`) |

### Valores de `status`

| Valor | Significado |
|---|---|
| `success` | Todos los pasos completados sin bloqueos. |
| `partial` | Algunos pasos completados; tareas pendientes reportadas al dev. |
| `blocked` | La skill no puede avanzar sin acción del dev. La razón está en `risks`. |

---

## Sección C — Review Workload Forecast

### Propósito

`/fg-design` calcula, al cerrar, una estimación del tamaño del PR resultante y decide qué hacer según el comportamiento configurado en `rules.pr_size`. Este bloque define el cálculo y las acciones.

### Cómo leer la configuración

Del `docs/auditoria/config.yaml` del proyecto:

```yaml
rules:
  pr_size:
    budget_lines: 400       # umbral de "PR grande"
    suggest_split: false    # ¿sugerir partir en chained PRs?
    enforcement: off        # off | warn | block
```

### Cálculo de la estimación

Al final de `/fg-design`, estimar las líneas cambiadas del PR resultante:

- Contar los archivos en "Archivos afectados" de `diseño.md`.
- Estimar líneas por archivo según tipo (nuevos archivos: tamaño completo estimado; modificados: delta estimado).
- Sumar para obtener `estimated_changed_lines`.

### Modos de enforcement

| Modo | Comportamiento |
|---|---|
| `off` | No mencionar el budget en ningún momento. Terminar inmediatamente. 1 issue = 1 MR sin fricción. |
| `warn` | Si `estimated_changed_lines > budget_lines`: emitir bloque informativo. No bloquear. Continuar. |
| `block` | Si `estimated_changed_lines > budget_lines`: pedir al dev `size:exception` documentada antes de continuar. No avanzar sin justificación. |

### Bloque de salida (campo `review_workload_forecast` en el envelope de `/fg-design`)

```yaml
review_workload_forecast:
  estimated_changed_lines: <N>
  budget_threshold: <budget_lines del config>
  budget_risk: Low | Medium | High
  chained_recommended: Yes | No
  decision_needed_before_apply: Yes | No
  suggested_split: <descripción del split, o "none" si no aplica>
```

Reglas para `budget_risk`:
- `Low`: `estimated_changed_lines <= budget_lines * 0.75`
- `Medium`: entre 75% y 100% del budget
- `High`: supera el budget

**Guard lines exactas** que DEBEN aparecer en el bloque de texto del forecast cuando se emite:

```
Decision needed before apply: Yes|No
Chained PRs recommended: Yes|No
400-line budget risk: Low|Medium|High
Estimated changed lines: N
```

### Cuándo emitir el forecast

- `enforcement: off` → NO emitir (silencio total).
- `enforcement: warn` → SIEMPRE emitir, incluso si el riesgo es bajo. Es información, no acción.
- `enforcement: block` → SIEMPRE emitir. Si riesgo es High, bloquear hasta recibir `size:exception`.

---

## Sección D — Delivery Strategy Negotiation

### Modos de delivery strategy

Cuando el forecast indica riesgo (`enforcement: warn` o `block`), mostrar al dev las opciones disponibles:

| Modo | Descripción |
|---|---|
| `single-pr` | Todo en un PR. Default de forge — 1 issue = 1 MR. |
| `ask-on-risk` | Preguntar al dev cuando el forecast supera el budget. |
| `auto-chain` | Partir automáticamente en chained PRs sin preguntar. |
| `exception-ok` | Continuar con PR grande documentando `size:exception`. |

### Chain strategies (cuando el dev elige chained PRs)

| Estrategia | Descripción |
|---|---|
| `stacked-to-main` | Cada PR apunta a `main` en orden. Iteración rápida, fix en el momento. |
| `feature-branch-chain` | Un tracker branch acumula trabajo. PRs hijo se acoplan al PR previo. Solo el tracker mergea a `main`. Mejor para rollback y releases coordinados. |

### Regla de no-acción (CRÍTICA)

**forge NUNCA crea ramas ni abre PRs sin opt-in explícito del dev.**

El forecast y la negociación son **información**, no acción. El dev que solo presiona "continuar" sin leer NO debe terminar con ramas o PRs inesperados. Antes de crear cualquier rama o PR, pedir confirmación explícita y que el dev elija la estrategia.

### Cache de sesión

Una vez que el dev eligió delivery strategy y chain strategy en una sesión, **no volver a preguntar** en el mismo ciclo. Reusar la elección cacheada.

---

## Sección E — Reglas de Idempotencia

### Regla E.1 — Nunca sobrescribir si el artefacto existe

Si un artefacto ya existe (ej: `/fg-design` se re-corre y `diseño.md` ya existe), **NO sobrescribir silenciosamente**. Opciones:

1. Preguntar al dev si quiere re-generar ese artefacto específico.
2. Reportar que el artefacto fue preservado y omitir la re-generación.

La regla aplica a: `README.md`, `diseño.md`, `tareas.md`, `decisiones.md`, `exploracion.md`, `docs/auditoria/config.yaml`, `CLAUDE.md`, `config/modulos-transversales.yaml`.

**Preservar > sobrescribir**: en caso de duda, preservar siempre.

### Regla E.2 — `decisiones.md` es append-only (estricta)

`decisiones.md` crece con el tiempo — cada decisión se agrega al final. **Nunca sobrescribir `decisiones.md`**. Si se detecta que hay contenido previo, hacer append en lugar de reescribir.

Esta regla es la más crítica: una sobrescritura de `decisiones.md` destruye el historial de decisiones técnicas del cambio.

### Regla E.3 — Verificar estado antes de crear

Antes de crear cualquier artefacto, verificar si ya existe:

```
¿Existe el artefacto?
  Sí → preservar (regla E.1) o hacer append (regla E.2)
  No → crear
```

Nunca asumir que el artefacto no existe sin verificar.

### Regla E.4 — Reportar lo que se preservó, creó o mergeó

Al cerrar, el envelope de retorno debe dejar claro:

```yaml
artifacts:
  - docs/auditoria/cambios/<cambio>/diseño.md (creado)
  - docs/auditoria/cambios/<cambio>/tareas.md (preservado — ya existía)
  - docs/auditoria/cambios/<cambio>/decisiones.md (mergeado — N entradas nuevas)
```

### Regla E.5 — `implement-progress` se mergea, nunca se sobrescribe

`/fg-implement` guarda progreso en engram bajo el topic_key `forge/{cambio}/implement-progress`. Si ya existe, **leer + mergear** las tareas completadas antes de guardar. Nunca llamar `mem_save` con el progreso nuevo sin incorporar el previo — eso borra el progreso histórico.

Pasos obligatorios:
1. `mem_search(query: "forge/{cambio}/implement-progress", project: "{project}")`.
2. Si existe: `mem_get_observation(id)` → parsear tareas `[x]` ya completadas.
3. Implementar nuevas tareas.
4. `mem_save` con topic_key `forge/{cambio}/implement-progress` con el contenido MERGED (previas `[x]` + nuevas `[x]`).
