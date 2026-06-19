# 08 — Un bugfix en ceremonia Rápido

## El dev y el sistema

El dev trabaja en un sistema de facturación electrónica Python. El módulo central es
`billing/tax_calculator.py`, con la función `calculate_order_taxes(order_lines)`.

El bug: el acumulador `Decimal` se redondea dentro del loop de líneas en vez de hacerlo
una sola vez al final. En órdenes con más de 10 líneas con IVA 21%, el total de impuestos
muestra $0.01 de diferencia respecto del valor correcto.

El sistema está en buen estado: `docs/arquitectura/` actualizada, suite de `pytest` verde,
forge configurado. La corrección implica mover un `round()` fuera del loop — dos o tres
líneas de código.

Configuración del proyecto relevante (`docs/auditoria/config.yaml`):

```yaml
rules:
  implement:
    tdd: false
  workflow:
    cycle_mode: interactive
    ceremonial_threshold: auto
```

## El disparador

El dev escribe en el chat:

> "hay un bug de redondeo en el cálculo de impuestos, el total de un pedido grande queda
> con $0.01 de diferencia"

No usa slash commands. El orquestador detecta la intención y arranca el ciclo.

## Paso a paso

### Paso 1 — Orquestador pregunta el modo de ciclo

Antes de arrancar el primer ciclo de la sesión, el orquestador pregunta:

> "¿Querés correr este ciclo en modo interactivo (pausa entre fases) o automático
> (encadena sin pausa)?"

Esta pregunta ocurre una única vez por sesión, antes del primer ciclo. La respuesta se
cachea en memoria de sesión y no se persiste en filesystem (`fg-phase-common.md:23`).
Sesión nueva implica pregunta nueva.

---

### Paso 2 — Dev elige modo automático

El dev responde: "automático". El orquestador cachea `cycle_mode=automatic` para esta
sesión.

A continuación evalúa el nivel de ceremonia. La descripción contiene "bug", "redondeo",
"diferencia" — el tipo inferido es `fix`. El orquestador aplica criterios contextuales:
scope reducido, sin palabras de escala ("migrar", "reescribir", "rediseñar"), sin cambios
de arquitectura declarados.

**Nota importante:** `fix` no está listado como "tipo ligero" en `guia-de-uso.md:290`,
que enumera explícitamente `docs/chore/test/style` como tipos que mapean a Rápido por
regla. El orquestador propone Rápido para este `fix` por juicio contextual — scope
pequeño, sin indicadores de escala — no por una regla documentada de "fix es siempre
ligero". Esta distinción es relevante: ante un `fix` de mayor complejidad, el orquestador
podría proponer Completo.

El orquestador también verifica la condición de arquitectura al día: ejecuta Grep sobre
`docs/auditoria/cambios/*/README.md` buscando frontmatter con `structural: true` sin
`arch_synced: true`. No encuentra ninguno — la arquitectura está sincronizada y Rápido
está disponible (`guia-de-uso.md:299-304`).

---

### Paso 3 — Orquestador propone el nivel de ceremonia

Con `ceremonial_threshold: auto`, el orquestador PROPONE el nivel y ESPERA confirmación
del dev antes de avanzar (`guia-de-uso.md:282-283`):

> "Este es un fix puntual de redondeo, scope reducido, arquitectura al día. Propongo
> Rápido: /fg-plan → /fg-implement → /fg-review (sin /fg-design). /fg-review siempre
> corre. ¿Confirmás?"

---

### Paso 4 — Dev confirma Rápido

El dev responde: "sí, Rápido". El orquestador registra `nivel=Rápido` para este cambio y
delega a `/fg-plan`.

El nivel de ceremonia queda determinado antes de invocar la skill. `/fg-plan` nunca lo
re-evalúa (`fg-plan.md:176`).

---

### Paso 5 — `/fg-plan` infiere tipo, nombre y contexto

Antes de ejecutar, `/fg-plan` corre el gate de re-detección lazy (`fg-phase-common.md`,
Sección A — `needs_detection()`). El stack no cambió desde el último ciclo — la detección
no se repite.

La skill ejecuta:

1. **Inferencia de tipo:** `fix` — descripción contiene "bug", "redondeo", "diferencia"
   (`fg-plan.md:46`).

2. **Nombre kebab-case:** extrae palabras clave significativas: "redondeo", "calculo",
   "impuestos". Elimina conectores. Resultado: `redondeo-calculo-impuestos` (3 palabras,
   dentro del límite de 4-5 palabras significativas, `fg-plan.md:59`).

3. **Contexto:** `docs/arquitectura/overview.md` existe → Branch 2. Lee `overview.md`
   como contexto primario. Consulta `mcp__codegraph__codegraph_explore` para
   `billing/tax_calculator.py` como contexto secundario (`fg-plan.md:91-98`).

4. **Sin ambigüedad:** tipo y nombre se infieren sin bifurcación — no pregunta sobre
   naming.

5. **Pregunta sobre alcance del problema** (`fg-plan.md:125-128`):
   > "¿El bug se da solo con IVA 21%, o también con otras alícuotas? ¿Hay alguna
   > restricción de compatibilidad con la lógica de redondeo de proveedores externos?"

---

### Paso 6 — Dev aclara el alcance

El dev responde: "pasa con cualquier alícuota cuando hay más de 10 líneas. Sin
restricciones de proveedores externos, el cálculo es 100% interno."

`/fg-plan` completa el contexto y genera los artefactos:

- Crea `docs/auditoria/cambios/2026-06-fix-redondeo-calculo-impuestos/` con fecha YYYY-MM
  del mes actual (`fg-plan.md:75`).
- Genera `README.md` desde `templates/README-change.md`. Estado inicial: `planeado`.
  Sección Cierre vacía (`fg-plan.md:132-142`).
- En modo Rápido, `/fg-plan` también genera `tareas.md` desde `templates/tareas-lite.md`
  — este archivo lo crea la skill de plan, no `/fg-design` que no corre en este modo
  (`fg-plan.md:172`).

**Artefactos creados en este paso:**
- `docs/auditoria/cambios/2026-06-fix-redondeo-calculo-impuestos/README.md`
- `docs/auditoria/cambios/2026-06-fix-redondeo-calculo-impuestos/tareas.md`

---

### Paso 7 — `/fg-plan` reporta al dev y entrega el `tareas.md`

La skill reporta: ruta creada, tipo `fix`, nombre `redondeo-calculo-impuestos`, y que el
siguiente paso es `/fg-implement` (no `/fg-design` — Rápido no incluye esa fase,
`fg-plan.md:190`).

El `tareas.md` generado desde `templates/tareas-lite.md` lleva el header canónico
"Generado por /fg-plan en modo Rápido". El template tiene placeholders (`Tarea 1`,
`Tarea 2`) con instrucciones integradas para que `/fg-plan` derive tareas concretas del
README. El checklist resultante contiene tareas de granularidad TDD-sized:

- `[ ]` Reproducir la falla: test multi-línea que evidencia $0.01 de diferencia
- `[ ]` Corregir acumulación en `calculate_order_taxes`: redondear solo al final del loop
- `[ ]` Verificar alícuotas alternativas (IVA 10.5%, percepciones)
- `[ ]` Confirmar que los tests de 1-2 líneas preexistentes siguen pasando

El contrato de `tareas.md` para `/fg-implement` es idéntico al de modo Completo: tareas
concretas, accionables, tachables.

---

### Paso 8 — Orquestador encadena a `/fg-implement` (modo automático)

Con `cycle_mode=automatic` cacheado en sesión, el orquestador no pausa para confirmación
entre fases. Delega inmediatamente a `/fg-implement` (`guia-de-uso.md:356`).

---

### Paso 9 — `/fg-implement` ejecuta las tareas

Antes de ejecutar, la skill corre el gate de re-detección lazy. Stack sin cambios — omite
re-detección.

Secuencia de ejecución:

1. **Lee `tareas.md`** — checklist presente y con tareas concretas.

2. **Busca `diseño.md`** — no existe. Modo Rápido válido y documentado: usa `README.md`
   como contexto de enfoque en su lugar (`fg-implement.md:46-49`). No aborta ni advierte
   por la ausencia.

3. **Lee `config.yaml`:** `rules.implement.tdd=false` → modo estándar. Avisa al dev:
   "TDD Strict no está activo. Corriendo en modo estándar." (`fg-implement.md:33-34`).

4. **Verifica batching:** 4 tareas < `max_tasks_per_batch=20` → caben en un solo batch
   (`fg-implement.md:59-65`).

5. **Safety Net** (`fg-phase-common.md`, Sección A): corre los tests preexistentes que
   cubren `billing/tax_calculator.py` y captura el baseline. Pasan — el orquestador
   continúa. El Safety Net NO escribe tests nuevos; solo verifica el estado de los
   existentes antes de tocar el código.

6. **Implementa cada tarea en orden:** primero el test de regresión multi-línea que
   reproduce la falla, luego la corrección en `calculate_order_taxes` (mover `round()`
   fuera del loop), luego los casos adicionales de alícuota, finalmente confirma que los
   tests preexistentes de 1-2 líneas siguen verdes.

7. **Tacha cada tarea en `tareas.md`** al completarla.

8. **Actualiza `README.md`:** cambia Estado a `implementado` (`fg-implement.md:129`).

9. **`evidencia-tdd.md` NO se genera.** Con `rules.implement.tdd=false`, el archivo no
   se crea. El envelope de `/fg-implement` es explícito: "solo si TDD activo"
   (`fg-implement.md:188`). En modo estándar, no hay archivo de evidencia TDD a disco.

10. **`decisiones.md`:** si durante la implementación surge una decisión no trivial o
    una desviación del plan (por ejemplo, detectar que la corrección requiere ajustar
    también la función auxiliar de redondeo), la skill crea `decisiones.md` con entrada
    append-only (`fg-implement.md:107-108`). Si la implementación sigue el plan sin
    desvíos, el archivo puede no crearse — en modo Rápido esto es normal.

---

### Paso 10 — Orquestador encadena a `/fg-review` (modo automático)

El orquestador verifica que todas las tareas en `tareas.md` estén tachadas — condición
de entrada de `/fg-review` (`fg-review.md:29-30`). Están. Encadena sin pausa.

---

### Paso 11 — `/fg-review` evalúa el cambio e invoca roles

Antes de ejecutar, gate de re-detección lazy. Stack sin cambios — omite.

Secuencia:

1. **Lee contexto:** `diseño.md` no existe → fallback a `README.md` del cambio para
   sub-agentes, con nota explícita de que el contexto de diseño viene del README
   (`fg-review.md:45-47`). Lee `tareas.md` y `config.yaml`. Si `decisiones.md` existe,
   lo incorpora; si no existe (caso frecuente en Rápido), lo omite.

2. **Corre la suite completa de `pytest`.**

3. **`rules.implement.tdd=false` → validación básica:** no ejecuta TDD Compliance Check,
   no ejecuta Assertion Quality Audit, no ejecuta Changed File Coverage audit
   (`fg-review.md:35`). Avisa al dev que está en modo estándar.

4. **Invoca roles de review:**
   - `code-reviewer`: SIEMPRE (`fg-review.md:106`). Recibe `README.md` como contexto de
     diseño (fallback de `diseño.md`). `decisiones.md` se omite si no existe.
   - `security-reviewer`: NO. El path `billing/tax_calculator.py` no contiene patrones
     `*auth*/*login*/*password*` ni similares. Para dispararse por este cambio debería
     haber `flags_for_review` en el envelope de `/fg-implement` — no los hay.
   - `dba-reviewer`: NO (sin migraciones).
   - `frontend-reviewer`: NO (sin UI).
   - `qa-reviewer`: NO (tests son unit tests simples, sin integración compleja).
   - `legacy-impact-analyzer`: NO (`is_legacy=false`).

5. **Detección de cambios estructurales:** solo `billing/tax_calculator.py` modificado,
   no es un manifiesto ni módulo transversal marcado → `structural=false`
   (`fg-review.md:128-135`). No sugiere `/fg-update-arch`.

6. **Escribe sección Cierre en `README.md`** y actualiza Estado a `cerrado`
   (`fg-review.md:157-170`).

---

### Paso 12 — `/fg-review` reporta al dev

Resumen ejecutivo: suite completa verde, `code-reviewer` sin CRITICALs (1 SUGGESTION
menor sobre nombre de variable), cambio no estructural, Estado del README actualizado a
`cerrado`.

El cambio queda listo para commit. El dev hace el commit manualmente con el mensaje
convencional que considere apropiado — `/fg-review` no formula ni sugiere un mensaje de
commit específico. Forge solo documenta que el dev comitea a mano con la convención del
proyecto.

## Qué pregunta forge y cuándo

| Pregunta | Momento | Se cachea / persiste |
|---|---|---|
| ¿Modo interactivo o automático? | Paso 1 — antes del primer ciclo de la sesión | Cacheado en memoria de sesión. No persiste. Sesión nueva = pregunta nueva. |
| ¿Confirmás nivel Rápido? | Paso 3 — después de verificar arch al día y evaluar scope | No persiste. Confirmación puntual para este cambio. |
| ¿El bug se da solo con IVA 21%? ¿Restricciones de proveedores? | Paso 5 — dentro de `/fg-plan`, después de inferir tipo/nombre y resolver contexto | No persiste. Se usa para completar `README.md`. |

## Artefactos que quedan

```
docs/auditoria/cambios/2026-06-fix-redondeo-calculo-impuestos/
├── README.md        — portada del cambio (Qué/Por qué/Alcance/Restricciones);
│                      Estado evoluciona: planeado → implementado → cerrado;
│                      sección Cierre completada por /fg-review al final.
├── tareas.md        — generado por /fg-plan desde templates/tareas-lite.md;
│                      todas las tareas tachadas por /fg-implement al finalizar.
└── decisiones.md    — OPCIONAL: solo se crea si /fg-implement registra
                       decisiones no triviales o desviaciones del plan.
                       En Rápido sin desvíos puede no existir.
```

`evidencia-tdd.md` **no se crea** — `rules.implement.tdd=false` en este proyecto.

## Fricciones y casos borde

**Arquitectura desactualizada eleva el nivel:** si existiera cualquier cambio previo con
`structural: true` sin `arch_synced: true` en `docs/auditoria/cambios/*/README.md`, el
orquestador elevaría a Completo aunque el dev haya pedido Rápido. El dev sería informado,
no bloqueado en silencio (`guia-de-uso.md:302-305`).

**`fix` no garantiza Rápido por regla:** la guía documenta `docs/chore/test/style` como
tipos explícitamente ligeros. Para un `fix`, el orquestador aplica juicio contextual
(scope, ausencia de palabras de escala, arch al día). Un `fix` que implique múltiples
módulos interdependientes, migración de datos o cambio de contrato puede recibir propuesta
de Completo.

**`ceremonial_threshold: auto` siempre pregunta:** con esta configuración, el orquestador
propone y espera confirmación incluso para un fix de dos líneas. Si el dev prefiere cero
fricciones para fixes pequeños, puede configurar `ceremonial_threshold: lite` en
`config.yaml` — eso sesga hacia Rápido para tipos de scope reducido sin preguntar.

**`tareas.md` en Rápido y granularidad:** el template `templates/tareas-lite.md` tiene
placeholders pero incluye instrucciones integradas para que `/fg-plan` derive tareas
concretas del README. Las tareas resultantes son siempre concretas, no genéricas. Sin
embargo, sin el análisis de enfoque que hace `/fg-design` con CodeGraph, si el bug fuera
más complejo (múltiples módulos interdependientes), las tareas podrían quedar
subgranuladas.

**Fallback de `diseño.md` en sub-agentes:** `/fg-review` notifica explícitamente a cada
sub-agente que el contexto de diseño viene del README, no de `diseño.md`
(`fg-review.md:45-46`). La calidad del review es algo menor que en Completo porque el
README tiene menos detalle técnico que `diseño.md`. Para este fix de 2-3 líneas el
impacto es mínimo.

**`decisiones.md` puede no existir en Rápido:** `/fg-review` lo busca pero lo omite si
no está presente (`fg-review.md:47`). El `code-reviewer` recibe `README.md` como único
contexto de diseño.

**No existe `--rapido` que fuerce incondicionalmente:** si la arquitectura está
desactualizada o la descripción contiene palabras de escala, el orquestador aplica
Completo de todas formas aunque el dev intente forzar Rápido
(`guia-de-uso.md:319-321`).

## Límites observados

**Scope de repositorio único:** si el cálculo de impuestos estuviera partido entre
`billing-service` y `tax-rules-service` como dos repos separados, forge no tiene soporte
cross-repo. Cada repo debe adoptar forge por separado. Las dependencias entre repos quedan
fuera de visibilidad del ciclo.

**"Al día" depende de lo que forge sabe:** la verificación de arquitectura sincronizada
es confiable hasta donde forge tiene registro. Cambios manuales externos al ciclo forge
(un dev edita `billing/tax_calculator.py` directamente sin pasar por forge) no generan
marcas `structural/arch_synced`. "Al día" no garantiza que el repo no haya tenido cambios
estructurales fuera del ciclo (`guia-de-uso.md:306-309`).

**TDD Strict desactivado por defecto:** `rules.implement.tdd: false` es el default.
`/fg-implement` corre en modo estándar y solo avisa al dev. Si el dev quiere el ciclo
RED → GREEN → TRIANGULATE obligatorio, debe editar `config.yaml` manualmente.

**Sin commits ni PRs automáticos:** forge nunca crea ramas ni pull requests. El dev hace
el commit a mano con el mensaje convencional que defina. Esto aplica en todos los niveles
de ceremonia.

**`/fg-review` no sugiere mensajes de commit:** el workflow termina con el Estado del
cambio en `cerrado` y el resumen del review. Formular el mensaje de commit convencional es
responsabilidad del dev.

## Qué aprendimos

- **Rápido no es solo "más rápido":** tiene una precondición real y verificable —
  arquitectura al día. La verificación es automática mediante Grep de frontmatter en
  READMEs de cambios previos. Si falla, el orquestador eleva a Completo sin que el dev
  tenga que hacer nada.

- **`fix` no es tipo ligero por regla documentada:** `guia-de-uso.md:290` lista
  `docs/chore/test/style` como tipos explícitamente ligeros. Para un `fix`, el
  orquestador aplica juicio contextual de scope y escala. El resultado (Rápido o Completo)
  depende de la descripción y el contexto, no de una regla fija.

- **En Rápido, `tareas.md` lo genera `/fg-plan` — no `/fg-design`:** el template es
  `templates/tareas-lite.md`. El contrato de tareas concretas y tachables para
  `/fg-implement` es idéntico al de modo Completo; lo que cambia es la profundidad del
  análisis previo.

- **`evidencia-tdd.md` solo existe cuando `tdd=true`:** con TDD Strict desactivado,
  `/fg-implement` no escribe ese archivo a disco (`fg-implement.md:188`). El envelope
  devuelve información del Safety Net, pero sin persistencia en filesystem.

- **El modo de ciclo lo pregunta el orquestador una única vez por sesión,** antes del
  primer ciclo. No lo pregunta `/fg-plan` ni `/fg-design`. La respuesta se cachea en
  memoria de sesión y nunca persiste — sesión nueva implica pregunta nueva.

- **El contraste con Completo es concreto:** Completo agregaría `/fg-design` entre
  `/fg-plan` y `/fg-implement`. `/fg-design` produciría `diseño.md` (enfoque técnico,
  decisiones de arquitectura) y un `tareas.md` más detallado con análisis de CodeGraph
  sobre los archivos afectados reales. Los sub-agentes de `/fg-review` recibirían
  `diseño.md` en vez del README como contexto, produciendo un review más preciso. Para
  un fix de 2-3 líneas sin implicaciones de arquitectura, ese overhead no agrega valor
  real — Rápido es la ceremonia correcta.
