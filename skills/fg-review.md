---
name: fg-review
description: Valida y cierra el cambio. Carga strict-tdd-verify.md, corre la suite completa, valida la TDD Cycle Evidence, audita assertion quality, invoca sub-agentes especialistas según el cambio (única skill SDD que delega), detecta cambios estructurales y escribe la sección Cierre del README.
when_to_apply: El dev invoca /fg-review después de /fg-implement. Es el cuarto paso del workflow y la única skill SDD que puede delegar a sub-agentes especialistas.
---

# /fg-review

## Propósito

Validar que la implementación es correcta, que el TDD se aplicó realmente (no solo se reportó), que la calidad de los tests es real (no triviales), y consolidar el cierre del cambio con miradas especializadas si corresponde. Es la única skill del workflow SDD que **puede delegar a sub-agentes** — modelo de delegación C.

## Cuándo aplicarla

Después de `/fg-implement`, cuando el `design.md` tiene el checklist completo (todas las tareas tachadas) y se reportó la TDD Cycle Evidence. Si hay tareas sin terminar, abortar y reportar.

## Carga obligatoria del módulo Strict TDD Verify

Si en engram existe `forge/testing-capabilities/{project}` con `strict_tdd: true`, cargar el módulo `_shared/strict-tdd-verify.md` (vive en `mvp/skills/_shared/strict-tdd-verify.md` cuando forge se instala). Ese módulo define el TDD Compliance Check, el Assertion Quality Audit, Test Layer Distribution, Changed File Coverage y Quality Metrics.

Si `strict_tdd: false`, correr en modo estándar (validación básica) y avisar al dev.

## Proceso

### 1. Leer el contexto

- `design.md` del cambio: checklist, decisiones técnicas, flags_for_review (si vienen de `/fg-implement`).
- `README.md`: Estado actual.
- `apply-progress` y la TDD Cycle Evidence que generó `/fg-implement`.

### 2. Correr la suite completa de tests

No solo los nuevos — la suite completa del proyecto (o la subset relevante según testing capabilities). Si algo falla:

- Si la falla es del cambio actual: bloquear el review y reportar.
- Si la falla parece pre-existente (regresión no relacionada): flagear como WARNING pero no bloquear, dejar que el dev decida.

### 3. TDD Compliance Check (si Strict TDD activo)

Cruzar la TDD Cycle Evidence reportada por `/fg-implement` contra la realidad:

- ¿Existen los archivos de test listados?
- ¿Los tests pasan cuando se re-ejecutan ahora?
- ¿La cantidad de test cases por tarea coincide con lo reportado en TRIANGULATE?
- ¿El SAFETY NET se aplicó donde se modificaron archivos pre-existentes?

Si algo no cuadra, flagear como CRITICAL.

### 4. Assertion Quality Audit (si Strict TDD activo)

Escanear todos los tests creados o modificados en el cambio. Buscar **banned assertion patterns**:

- Tautologías (`expect(true).toBe(true)`) → CRITICAL.
- Ghost loops (assertion dentro de un for sobre colección potencialmente vacía) → CRITICAL.
- Empty collections sin compañero non-empty → WARNING.
- Type-only assertions solas (`toBeDefined()` sin value assertion) → WARNING.
- Smoke tests solos (`render() + toBeInTheDocument()` sin behavioral) → WARNING.
- CSS class assertions (`expect(el.className).toContain(...)`) → WARNING.
- Mock-heavy tests (mocks > 2× expects) → WARNING.

Reportar la tabla con file/line/assertion/issue/severity.

### 5. Test Layer Distribution y Changed File Coverage

- Clasificar tests por layer (Unit / Integration / E2E).
- Si hay tool de coverage en testing capabilities, correr coverage sobre archivos modificados y reportar por archivo con líneas no cubiertas.

### 6. Quality Metrics (si tools disponibles)

- Linter sobre archivos cambiados.
- Type checker (filtrado a archivos cambiados).
- Reportar errores y warnings.

### 7. Invocar sub-agentes especialistas según el cambio

**Esta es la única parte del workflow SDD donde una skill delega.**

Reglas de invocación (cada una usa la tool `Agent` con el `subagent_type` correspondiente):

- **Siempre**: `code-reviewer` (review general).
- **Si el cambio toca auth, datos sensibles o endpoints públicos**: `security-reviewer`. Detectar por path (`*auth*`, `*login*`, `*password*`, etc.) o por flags_for_review del envelope de `/fg-implement`.
- **Si hay migraciones o queries pesadas**: `dba-reviewer`. Detectar por path (`*migrations*`, `*.sql`) o por flags_for_review.
- **Si toca UI/UX**: `frontend-reviewer`. Detectar por path (`*.tsx`, `*.jsx`, `components/`, `pages/`).
- **Si hay tests complejos o de integración nuevos**: `qa-reviewer`.
- **Si el proyecto está marcado como legacy** (config del proyecto o tag en `docs/architecture/`): `legacy-impact-analyzer`.

Para cada role invocado:

1. Llamar a `Agent({subagent_type: "<role>", description: "<breve>", prompt: "<contexto + diff + design.md relevante>"})`.
2. Esperar el envelope de retorno.
3. Si retorna issues CRITICAL: incluirlos en el cierre como bloqueantes.
4. Si retorna issues WARNING/SUGGESTION: incluirlos en el cierre como observaciones.

### 8. Detectar cambios estructurales con CodeGraph

Correr el detector de cambios estructurales (`forge/structural_detector.py`). Marcar el cambio como estructural si:

- Toca archivos de manifiesto (`requirements.txt`, `package.json`, `go.mod`, etc.) — nueva dependencia.
- CodeGraph detecta módulos top-level nuevos.
- CodeGraph detecta cambios en módulos marcados como transversales (config `modulos-transversales.yaml`).
- Hay archivos de migración de BD.

Si es estructural, agregar al frontmatter del `README.md`:

```yaml
---
structural: true
---
```

### 9. Sugerir `/fg-update-arch` si corresponde

Si el cambio fue marcado como estructural, sugerirle al dev correr `/fg-update-arch` antes de cerrar. No invocarla automáticamente — el dev decide.

### 10. Escribir la sección Cierre del README.md

Sintetizar todo en la sección "Cierre":

- Qué quedó hecho (resumen del scope final).
- Qué se difirió a otros cambios (si aplica).
- Resultado de cada role invocado (tabla con role + status + comentarios).
- Resultado de la validación TDD (TDD Compliance + Assertion Quality + Coverage).
- Si es estructural y se sugirió `/fg-update-arch`.

### 11. Actualizar el README.md

Cambiar Estado a `cerrado`.

### 12. Reportar al dev

- Resumen ejecutivo del review.
- Issues CRITICAL si hay (bloquean el cierre).
- Issues WARNING/SUGGESTION (informativos).
- Sugerencia de `/fg-update-arch` si aplica.

## Reglas

### Siempre

- Cargar el módulo Strict TDD Verify si está activo.
- Correr la suite completa, no solo los tests nuevos.
- Validar la TDD Cycle Evidence contra ejecución real.
- Invocar `code-reviewer` por default.
- Invocar roles especializados según las condiciones de detección.
- Detectar cambios estructurales con CodeGraph + parser de manifiestos.
- Escribir la sección Cierre del README con síntesis de todos los reviews.
- Tests que fallan ahora pero pasaron en `/fg-implement` → CRITICAL.

### Preguntar

- Cuando un role retorna issues que son ambiguos (¿son CRITICAL o WARNING?), preguntar al dev.
- Cuando la falla de un test es de scope ambiguo (¿pre-existente o introducida acá?), preguntar.

### Nunca

- Delegar a otras skills SDD (`/fg-plan`, `/fg-design`, `/fg-implement`, `/fg-update-arch`). Solo a roles.
- Modificar el código del cambio (eso es trabajo de `/fg-implement`, no de `/fg-review`).
- Arreglar issues encontrados — solo reportar.
- Cerrar el cambio si hay tests fallando del propio cambio.
- Saltarse el Assertion Quality Audit cuando Strict TDD está activo.
- Invocar `/fg-update-arch` automáticamente — solo sugerirla.

## Envelope de retorno

```yaml
status: success | partial | blocked
executive_summary: 1-2 oraciones del resultado del review
artifacts:
  - docs/audit/changes/<cambio>/README.md (Cierre escrito, Estado: cerrado)
tests_run:
  total: <N>
  passing: <N>
  failing: <N>
  pre_existing_failures: <N>
tdd_compliance:
  evidence_reported: ✅ / ❌
  red_confirmed: ✅ / ⚠️
  green_confirmed: ✅ / ❌
  triangulation_adequate: ✅ / ⚠️ / ➖
  safety_net: ✅ / ⚠️
assertion_quality:
  critical: <N>
  warning: <N>
  issues: <tabla con file/line/issue>
coverage:
  average_changed_files: <%>
  files_below_80: <lista>
roles_invoked:
  - role: code-reviewer
    status: <success / issues>
    critical: <N>
    warning: <N>
  - role: <otros si aplica>
structural: true | false
suggest_update_arch: true | false
next_recommended: /fg-update-arch (si estructural) | None (cambio cerrado)
risks: None | <riesgos detectados>
```
