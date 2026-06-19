# 01 — Greenfield sin documentación: dev fundador arranca desde cero

Escenario de referencia para directorio vacío. Cubre el ciclo completo
`/fg-setup` (modo bootstrap) → `/fg-update-registry` → `/fg-plan` → inicio de
`/fg-design`, con el primer cambio incremental ya acotado.

---

## El dev y el sistema

**Persona:** fundador técnico en solitario. Construye un producto de gestión de
turnos para clínicas. No hay código, no hay PRD, no hay repositorio git.
Acaba de instalar forge y quiere la disciplina de auditoría desde el día uno,
pero también quiere empezar a codear rápido.

**Dominio:** app web single-tenant para una clínica. Usuarios: recepcionistas,
profesionales (médicos), administrador. Funciones previstas: pacientes,
profesionales, agenda/calendario de turnos. Stack mencionado: backend
Python/FastAPI, frontend React, base de datos Postgres, auth con
email+password. El dev no menciona pagos, notificaciones ni multi-clínica.

**Estado inicial del directorio:** `C:\dev\clinica-turnos\` existe y está vacío.
No hay `.forge/`, no hay `.git/`, no hay ningún manifiesto (`pyproject.toml`,
`package.json`, etc.).

---

## El disparador

El dev abre Claude Code dentro de `C:\dev\clinica-turnos\` y escribe en
lenguaje natural:

> "Quiero construir una app web para gestionar los turnos de una clínica:
> pacientes, profesionales y la agenda de citas."

forge es **latente**: no es un proceso corriendo que hay que invocar. El
orquestador detecta la intención en el mensaje (`guia-de-uso.md:36`, tabla
"Cuándo forge entra"): un "quiero hacer un sistema de X" en un directorio sin
proyecto activo es la señal de entrada para inicializar, no para planear.
No hace falta que el dev escriba `/fg-setup`.

---

## Paso a paso

### Paso 1 — El orquestador reconoce el contexto y decide el punto de entrada

El orquestador lee la intención del dev. La combina con el estado del
directorio (vacío, sin `.forge/`) y concluye: el primer paso es setup en modo
bootstrap, no planning. Ref: `guia-de-uso.md:159-166` (Escenario 1).

forge no impone ninguna acción todavía. Primero **propone el nivel de
ceremonia**: una feature nueva en un proyecto sin historia sugiere modo
Completo. Espera confirmación del dev antes de avanzar. Con
`ceremonial_threshold:auto` (default), esta propuesta es siempre explícita; el
orquestador nunca impone el nivel sin consentimiento del dev.

### Paso 2 — Delegación a fg-setup

El orquestador NO ejecuta fg-setup inline. Lo delega al sub-agente fg-setup
mediante la primitiva de delegación nativa (Task / sub-agente). La skill
tiene un ORCHESTRATOR GATE explícito: si se carga vía tool `Skill`, la
ejecución la toma el executor, no el orquestador.
Ref: `skills/fg-setup.md:7-16`.

### Paso 3 — Detección de modo: bootstrap

fg-setup llama `bootstrap.detect_mode(root)`. La lógica es:

- `.forge/` presente → upgrade
- `.git/` o manifiesto conocido presente → adopt
- ninguno de los anteriores → **bootstrap**

El directorio vacío cae en bootstrap. La skill NO aborta: forge está diseñado
para inicializarse en un directorio vacío. Config resultante:
`pending_detection:true`, `stacks:[]`.
Ref: `skills/fg-setup.md:42-52`.

### Paso 4 — Oferta de git init (la pregunta la hace el orquestador)

Como no existe `.git/`, fg-setup **no pregunta inline** (es un sub-agente y no puede). Devuelve la decisión en `decisions_needed` y sigue con el setup sin git:

```yaml
decisions_needed:
  - question: "No encontré un repositorio git en el proyecto. ¿Querés que se corra git init?"
    options: [Sí, No]
    default: Sí
```

El **orquestador** lee eso y le pregunta al dev con `AskUserQuestion` (le aparece como formulario Sí/No). El dev elige "Sí"; el orquestador corre `git init` (o re-invoca el setup) y queda `git_initialized:true`.

Nota: el Python (`bootstrap.run()`) solo reporta si `.git/` existe o no; nunca corre git init.
Ref: `skills/fg-setup.md:53-60`; `skills/_shared/fg-phase-common.md` Sección B.1.

**Artefacto:** `.git/`

### Paso 5 — Stack y test runner: detección diferida

En modo bootstrap no hay manifiestos ni código que analizar. Los pasos de
detección de stack y test runner se saltan. `config.yaml` queda con
`pending_detection:true` y `stacks:[]`. El test runner queda `null`. La
detección se realizará cuando el dev agregue manifiestos y re-corra
`/fg-setup`.
Ref: `skills/fg-setup.md:50-52, 84-88`.

### Paso 6 — Creación de la estructura base

fg-setup crea los artefactos mínimos del proyecto. Lo que genera y lo que NO:

**Genera:**

- `docs/auditoria/config.yaml` con defaults conservadores:
  `cycle_mode:interactive`, `pr_size.enforcement:off`,
  `implement.tdd:false`, `max_tasks_per_batch:20`,
  `coverage_threshold:0`, `context.pending_detection:true`,
  `stacks:[]`.
- `docs/auditoria/guardrails.yaml` — plantilla de reglas del hook de
  guardrails. Se deposita siempre en todos los modos (bootstrap, adopt,
  upgrade); NO se sobreescribe si ya existe. El hook de guardrails lee
  este archivo en tiempo de ejecución para evaluar reglas; un bootstrap
  sin personalización usa los defaults del template.
  Ref: `forge/bootstrap.py:828` (función `create_guardrails_template`).
- `docs/auditoria/cambios/` — carpeta vacía, base de la cadena de auditoría.
- `config/modulos-transversales.yaml`.
- `.atl/skill-registry.md` — placeholder (índice real lo genera
  `/fg-update-registry` en el paso siguiente).
- `.gitignore` actualizado (`.codegraph/` completo; `.engram/` con
  excepción `.engram/chunks/`).

**NO genera:** `src/`, `docker-compose`, `Makefile`, `deploy/`, manifiestos de
dependencias, ni scaffolding del proyecto. El dev crea el código él mismo o a
través de `/fg-implement`.

**NO genera** `CLAUDE.md`: la doctrina del orquestador es global y viene de
`~/.claude/CLAUDE.md` vía `forge install`. No hay CLAUDE.md por proyecto.

Ref: `skills/fg-setup.md:90-173, 26-31, 152-154`; `guia-de-uso.md:178`.

**Artefactos:** `docs/auditoria/config.yaml`, `docs/auditoria/guardrails.yaml`,
`docs/auditoria/cambios/` (vacía), `config/modulos-transversales.yaml`,
`.atl/skill-registry.md` (placeholder), `.gitignore` (actualizado).

### Paso 7 — CodeGraph: inicialización degradada

fg-setup intenta inicializar CodeGraph. En un directorio vacío no hay código
que indexar: reporta 0 nodos, 0 aristas. No bloquea la continuación.

Si el binario de CodeGraph no estuviera disponible, fg-setup **no pregunta inline**: devuelve la decisión en `decisions_needed` (seguir degradado o instalarlo primero) y el orquestador la resuelve con el dev. En este caso el binario existe, pero no hay código.
Ref: `skills/fg-setup.md:156-161`; `skills/_shared/fg-phase-common.md` Sección B.1.

**Artefacto:** `.codegraph/` (vacío).

### Paso 8 — La visión hace falta: fg-setup la deriva al orquestador

El sub-flow de Visión corre **únicamente en modo bootstrap**, pero **fg-setup NO lo conduce**: es un sub-agente y no puede conversar con el dev. La fase solo chequea la idempotencia:

- Si `overview.md` ya existe → `vision_status:preserved`, se saltea.
- Si `vision_skipped:true` en config → devuelve `decisions_needed` ("¿Reintentar la visión?") para que el orquestador decida.
- Ninguna condición aplica aquí → fg-setup devuelve `vision_status:pending-orchestrator` y, en `decisions_needed`, la señal de que el orquestador debe conducir la conversación (con las 5 preguntas guía). El resto del setup (config, guardrails, CodeGraph, registry placeholder) ya quedó hecho — `pending-orchestrator` no bloquea esos artefactos.

Ref: `skills/fg-setup.md:181-216`; `skills/_shared/fg-phase-common.md` Sección B.1.

### Paso 9 — El orquestador conduce la conversación de visión

El **orquestador** (no la fase) le hace al dev las 5 preguntas guía, en texto libre:

1. ¿Qué es el sistema, quién lo usa, qué problema resuelve?
2. ¿Multi-tenant o single-tenant? ¿Qué roles de usuario?
3. ¿Web, mobile, CLI o API? ¿Estrategia de autenticación?
4. ¿Stack tecnológico?
5. ¿Módulos o áreas de negocio previstas?

El dev responde:

1. App para que una clínica gestione turnos. Resuelve el caos de agendar citas a mano. Usuarios: recepcionistas, profesionales, admin.
2. Single-tenant (una sola clínica por ahora). Roles: recepcionista, profesional, admin.
3. App web. Auth con email y password.
4. Backend Python con FastAPI, frontend React, base Postgres.
5. Módulos: pacientes, profesionales, agenda de turnos.

El dev cubrió los cinco temas, así que no hace falta una segunda ronda de calibración (que pediría solo lo no mencionado). El orquestador usa **exclusivamente lo dicho**: no inventa módulos (notificaciones, pagos, multi-clínica) ni decisiones técnicas no mencionadas.

### Paso 10 — El orquestador destila y confirma los drafts

El orquestador destila borradores de `overview.md` y `stack.md` con solo lo dicho, y se los muestra al dev:

- `overview.md`: clínica single-tenant, roles recepcionista/profesional/admin, módulos pacientes/profesionales/agenda.
- `stack.md`: FastAPI (Python), React, Postgres, auth email+password.

Pregunta la aceptación con `AskUserQuestion` (opciones discretas: **Aceptar / Editar / Rechazar**), así le aparece al dev como formulario clicable. El dev elige "Aceptar". ("Editar" permite una iteración de ajuste; "Rechazar" deja la visión saltada.)

### Paso 11 — Re-invocación: fg-setup escribe los docs

Con los drafts aceptados, el orquestador **re-invoca a fg-setup** pasándole el `overview_content` y el `stack_content`. fg-setup (idempotente) llama `bootstrap.create_arquitectura_docs(...)` y `bootstrap.patch_config_stacks(root, ['Python', 'Node'])` para actualizar `context.stacks` en `config.yaml`. `vision_status:completed`.

Si el dev hubiera rechazado, el orquestador informa el skip y fg-setup llama `mark_vision_skipped()`, persistiendo `vision_skipped:true` en config.

Ref: `skills/fg-setup.md:181-216` (paso 10 reescrito: la fase reporta, el orquestador conduce y re-invoca).

**Artefactos:** `docs/arquitectura/overview.md`, `docs/arquitectura/stack.md`, `docs/auditoria/config.yaml` (stacks parcheados).

Nota: `overview.md` y `stack.md` se generan **únicamente en modo bootstrap**. En modo adopt fg-setup no los crea.

### Paso 12 — Reporte final de fg-setup

La skill reporta al dev (en español):

- Modo: bootstrap.
- Stack detectado: ninguno (re-detecta cuando se agreguen manifiestos).
- CodeGraph: no inicializado (0 nodos).
- TDD: OFF por defecto. Para activarlo: editar `rules.implement.tdd: true` en
  `docs/auditoria/config.yaml`.
- Próximo paso obligatorio: `/fg-update-registry`.

Ref: `skills/fg-setup.md:238-260, 312`.

### Paso 13 — /fg-update-registry (paso obligatorio)

Tras un `/fg-setup` exitoso, el orquestador **DEBE** invocar
`/fg-update-registry` como siguiente paso. No es opcional.
Ref: `skills/fg-setup.md:166`.

`/fg-update-registry` genera el índice real de skills y lo escribe en
`.atl/skill-registry.md`, reemplazando el placeholder del paso 6.

**Artefacto:** `.atl/skill-registry.md` (índice real, reemplaza placeholder).

### Paso 14 — El dev pide "todo de una"

El dev dice: "Listo, ahora generame todo el sistema: pacientes, profesionales,
agenda, login, todo."

forge no tiene ese modo. La norma es 1 issue = 1 cambio, 1 sesión = 1 ciclo,
entrega incremental. Ref: `guia-de-uso.md:180-187`.

### Paso 15 — Pushback y acotamiento del primer slice

El orquestador hace pushback respetuoso (regla 3 "Push back on shortcuts"):
explica que forge entrega slice por slice y propone arrancar por un primer
cambio acotado.

El dev acepta y reformula: "Bueno, empecemos por la agenda: que un profesional
pueda definir sus horarios de atención."

El orquestador evalúa la ceremonia: feature nueva → propone modo Completo.
Espera confirmación del dev antes de avanzar.
Ref: `guia-de-uso.md:281-291`.

### Paso 16 — Pregunta de modo del ciclo (1x por sesión)

Como es el **primer ciclo de la sesión**, el orquestador pregunta el modo de
ejecución:

> "¿Este ciclo lo corro interactivo (pauso entre fases para que revises) o
> automático (encadeno hasta el final)? El default del proyecto es
> interactivo."

El dev responde "interactivo". La respuesta se cachea en **memoria de sesión**;
NO se persiste en filesystem. Una sesión nueva vuelve a preguntar.

El default viene de `rules.workflow.cycle_mode` en `config.yaml`; el orquestador
lo usa como valor pre-seleccionado pero siempre pregunta.
Ref: `skills/_shared/fg-phase-common.md:23`; `~/.claude/CLAUDE.md` sección
"Modo del ciclo SDD".

### Paso 17 — Delegación a fg-plan

El orquestador delega a fg-plan (sub-agente) con la descripción del dev.
fg-plan NO evalúa nivel de ceremonia: ese juicio ya lo hizo el orquestador.
El gate de delegación es idéntico al de fg-setup.
Ref: `skills/fg-plan.md:176, 7-16`.

Antes de ejecutar, fg-plan corre el gate de re-detección lazy
(`forge.bootstrap.needs_detection(root)`, `skills/_shared/fg-phase-common.md`
Sección A, paso 2). Como el proyecto quedó con `pending_detection:true` y no
se han agregado manifiestos, fg-plan reporta la situación claramente pero no
aborta: continúa con el contexto disponible (overview.md + CodeGraph vacío).

### Paso 18 — Inferencia de tipo y nombre

fg-plan infiere tipo y nombre con cero fricción de naming:

- "que un profesional pueda definir sus horarios" → tipo `feat` (feature nueva).
- Nombre kebab-case: `horarios-atencion-profesional` (keywords extraídos,
  conectores en español descartados, 4-5 palabras).

Crea la carpeta `docs/auditoria/cambios/2026-06-feat-horarios-atencion-profesional/`
usando el formato `YYYY-MM` (año-mes), NO fecha completa.
Ref: `skills/fg-plan.md:40-79, 160`.

**Artefacto:** `docs/auditoria/cambios/2026-06-feat-horarios-atencion-profesional/`

### Paso 19 — Resolución de contexto: Branch 2

fg-plan resuelve contexto en orden estricto:

1. `--from` → no aplica (no se pasó).
2. `overview.md` existe (recién creado) → **Branch 2**: usa overview.md como
   contexto primario vía `bootstrap.read_overview`.
3. CodeGraph → contexto secundario, vacío en este punto.

Branch 3b (abortar por falta de contexto) solo se activaría si overview.md
fuera `None` Y `stacks==[]` Y `vision_skipped==false`. No es el caso.
Ref: `skills/fg-plan.md:81-121`.

### Paso 20 — Clarificación del problema (no del naming)

fg-plan identifica huecos de **alcance y restricciones** (nunca el nombre) y los devuelve en `decisions_needed`; el **orquestador** se los pregunta al dev:

> "¿Los horarios son bloques recurrentes semanales o fechas puntuales?
> ¿Hay duración fija de turno por profesional?
> ¿Se contemplan excepciones/feriados en este slice?"

El dev acota: solo bloques semanales recurrentes y duración fija; feriados
quedan fuera por ahora.
Ref: `skills/fg-plan.md:123-131, 170`.

### Paso 21 — README.md del cambio

fg-plan genera `README.md` del cambio con las secciones:
Qué / Por qué / Alcance / Restricciones / Estado = `planeado`. La sección
Cierre queda vacía: la completa `/fg-review` al cerrar el ciclo.

En modo Completo fg-plan **únicamente escribe `README.md`**. No crea
`diseño.md` ni `tareas.md`: esos los genera `/fg-design` en la siguiente fase.
(En modo Rápido, `/fg-plan` sí crearía `tareas.md` desde
`templates/tareas-lite.md`.)

fg-plan sugiere `/fg-design` como siguiente paso.
Ref: `skills/fg-plan.md:132-149, 171-173`.

**Artefacto:**
`docs/auditoria/cambios/2026-06-feat-horarios-atencion-profesional/README.md`

### Paso 22 — Pausa interactiva y continuación del ciclo

En modo interactivo, el orquestador pausa al cerrar fg-plan y espera
confirmación del dev para continuar con `/fg-design`.

El dev confirma. El ciclo continúa:

- `/fg-design` requiere `README.md` (existe). Produce `diseño.md`,
  `tareas.md` y `decisiones.md`. Con CodeGraph vacío, el análisis de
  archivos afectados es limitado.
- `/fg-implement` corre en **modo estándar** porque `rules.implement.tdd:false`
  (default). No se escribe `evidencia-tdd.md` ni se ejecutan los 7 pasos del
  ciclo TDD. El archivo `evidencia-tdd.md` solo se crea cuando
  `rules.implement.tdd:true`.
- `/fg-review` es el piso innegociable (siempre corre salvo en modo Libre).
  Con `tdd:false`, corre en modo validación básica: NO ejecuta TDD Compliance
  Check, NI Assertion Quality Audit, NI Changed File Coverage audit. Sí corre
  `code-reviewer` (siempre) más los roles especialistas aplicables según paths
  y `flags_for_review` del envelope de `/fg-implement`.

Ref: `guia-de-uso.md:293-297`; `skills/fg-review.md:35`;
`skills/fg-implement.md:188`.

---

## Qué pregunta forge y cuándo

| Pregunta | Momento | Se cachea / persiste |
|---|---|---|
| ¿Correr git init? (Sí/No) | El orquestador, vía `AskUserQuestion`, cuando fg-setup reporta que no existe `.git/` (`decisions_needed`) | Acción inmediata. No se cachea. Reporta `git_initialized` en envelope. |
| 5 preguntas de Visión (qué es / tenant+roles / canal+auth / stack / módulos) | El orquestador, en texto libre, cuando fg-setup devuelve `vision_status:pending-orchestrator` (solo bootstrap) | El orquestador destila las respuestas; re-invoca fg-setup, que escribe `overview.md`/`stack.md` y parchea stacks en `config.yaml`. |
| 2da ronda de calibración: solo lo no mencionado | El orquestador, si quedó algo sin cubrir en la 1ra ronda | En este caso no hubo (el dev cubrió todo). |
| ¿Aceptás estos drafts? (Aceptar/Editar/Rechazar) | El orquestador, vía `AskUserQuestion`, tras destilar | "Aceptar" → re-invoca fg-setup que persiste los archivos. "Editar" → una iteración. "Rechazar" → `vision_skipped:true` en `config.yaml`. |
| ¿Interactivo o automático? (default del proyecto: interactivo) | El orquestador lo pregunta 1x por sesión, antes del primer ciclo | Cacheado en memoria de sesión. NO persistido. Sesión nueva → vuelve a preguntar. |
| ¿Bloques semanales o fechas puntuales? ¿Duración fija? ¿Feriados en este slice? | fg-plan, sobre el problema (nunca sobre el naming) | Volcado a `README.md` del cambio (Alcance / Restricciones). |

---

## Artefactos que quedan

```
C:\dev\clinica-turnos\
├── .git\
├── .atl\
│   └── skill-registry.md               ← índice real (tras /fg-update-registry)
├── .codegraph\                          ← vacío en bootstrap
├── .gitignore                           ← actualizado
├── config\
│   └── modulos-transversales.yaml
└── docs\
    ├── arquitectura\
    │   ├── overview.md                  ← destilado de la Visión
    │   └── stack.md                     ← destilado de la Visión
    └── auditoria\
        ├── config.yaml                  ← defaults + stacks parcheados
        ├── guardrails.yaml              ← plantilla del hook (no sobreescribir)
        └── cambios\
            └── 2026-06-feat-horarios-atencion-profesional\
                └── README.md            ← Estado: planeado
```

`/fg-design` agregará `diseño.md`, `tareas.md` y `decisiones.md` dentro de la
carpeta del cambio cuando se invoque en la siguiente fase.

---

## Fricciones y casos borde

**El dev pide "todo el sistema de una".**
forge no tiene ese modo. El orquestador hace pushback (regla 3), explica la
norma de entrega incremental y redirige a un slice acotado. Fricción real pero
alineada con la doctrina: 1 issue = 1 cambio.

**Stack no detectado tras el setup.**
`config.yaml` queda con `pending_detection:true`. Aunque el dev mencionó
FastAPI/React en la Visión, `patch_config_stacks` puede setear `stacks`, pero
el `test_runner` sigue `null` hasta que exista código real y se re-corra
`/fg-setup`. Cada skill fg-* corre el gate de re-detección lazy
(`forge.bootstrap.needs_detection(root)`, `skills/_shared/fg-phase-common.md`
Sección A, paso 2) antes de ejecutar. Mientras `pending_detection:true` y no
haya manifiestos, las skills reportan la situación claramente pero no abortan.

**CodeGraph vacío en el primer ciclo.**
`/fg-plan` opera en Branch 2 (overview como contexto primario) con CodeGraph
degradado. El primer `/fg-design` también tendrá contexto pobre de CodeGraph
hasta que exista código real para indexar.

**El modo interactivo/automático no se persiste.**
Si el dev cierra Claude Code y vuelve mañana, el orquestador vuelve a preguntar.
No hay forma de "ya lo configuré de forma permanente" para el modo del ciclo:
es intencional (el dev puede querer distinto por sesión).

**Interrupción durante la Visión.**
Si el sub-flow de Visión se interrumpe por budget de contexto LLM, no escribe
archivos parciales (`vision_status:incomplete`). En un proyecto con descripción
muy larga, hay riesgo de quedarse sin `overview.md`. Si esto ocurre, el dev
puede re-correr `/fg-setup`: la idempotencia detecta que `overview.md` no
existe y la Visión no está marcada como skipped, por lo que reintenta.

**Dev que declina la Visión.**
Si el dev elige "Rechazar" el draft (o declina las preguntas), el orquestador informa el skip y `overview.md`
y `stack.md` no se generan. `/fg-plan` operará en Branch 3c (contexto
desconocido, modo degradado): puede continuar pero con contexto limitado.

**Nota sobre el log PII.**
El hook PII no registra prompts limpios. Solo escribe en
`.forge/auditoria-pii.jsonl` cuando detecta y redacta PII (`action:redacted`),
cuando se usa `#fg-pass` o `FORGE_PII_DISABLE` (`action:passthrough`), o
cuando hay un error. Un prompt sin datos sensibles pasa en silencio, sin
entrada en el log.
Ref: `forge/filters/hook_user_prompt.py:81-83`.

---

## Límites observados

**forge no scaffoldea el proyecto.** No crea `src/`, `docker-compose`,
`Makefile`, `deploy/`, ni manifiestos de dependencias. El dev construye el
código él mismo o a través de `/fg-implement`. `/fg-setup` solo arma
`docs/` y `config/`.

**No hay CLAUDE.md por proyecto.** La doctrina del orquestador es global
(`~/.claude/CLAUDE.md` vía `forge install`). Un dev que espere un `CLAUDE.md`
en la raíz del proyecto no lo encontrará.

**No existe modo "generar el sistema entero".** La entrega es slice por slice,
1 sesión = 1 ciclo. El orquestador hace pushback si el dev lo pide.

**No hay soporte cross-repo / microservicios.** forge opera por raíz de
proyecto. Si la clínica luego separa backend y frontend en repos distintos,
hay que adoptar forge en cada repo por separado con `/fg-setup`.

**forge nunca crea ramas ni PRs automáticamente.** El `git init` es la única
acción git que ofrece, y con consentimiento explícito. Ramas y PRs son siempre
opt-in del dev.

**En bootstrap, la detección de stack/test runner queda pendiente.** El modo
es "al día hasta donde forge sabe". No hay análisis de código porque no hay
código. El `test_runner` es `null` hasta que exista código real.

**`overview.md` y `stack.md` se generan solo en bootstrap.** En modo adopt
(proyecto existente), `/fg-setup` no los crea. Solo el bootstrap + Conversación
de Visión los genera.

**La Visión destila solo lo dicho.** Si el dev olvida mencionar un módulo
(ejemplo: notificaciones), no aparecerá en `overview.md`. Es deliberado
(forge nunca inventa), pero exige que el dev sea completo en las respuestas,
o que agregue lo faltante después con `/fg-update-arch`.

**TDD off por default.** Con `rules.implement.tdd:false`, `/fg-implement` corre
en modo estándar, no escribe `evidencia-tdd.md`, y `/fg-review` no ejecuta
validaciones de ciclo TDD. Para activarlo: editar `config.yaml`.

---

## Qué aprendimos

- En un directorio vacío, forge entra por intención en lenguaje natural y
  selecciona modo bootstrap automáticamente. No hace falta invocar `/fg-setup`
  manualmente.

- La Conversación de Visión la conduce el **orquestador**; destila `overview.md` y `stack.md` usando
  exclusivamente lo que el dev dijo. No infiere módulos ni decisiones técnicas
  no mencionadas. Un dev que olvide un módulo puede agregarlo después con
  `/fg-update-arch`.

- `/fg-setup` genera siempre `docs/auditoria/guardrails.yaml` (en todos los
  modos: bootstrap, adopt, upgrade). Esta plantilla es la que el hook de
  guardrails lee en tiempo de ejecución. Ignorar este archivo es ignorar las
  reglas de evaluación del hook.

- `/fg-update-registry` es el paso obligatorio inmediato tras `/fg-setup`. Sin
  él, `.atl/skill-registry.md` sigue siendo un placeholder y el índice de
  skills no refleja el estado real.

- El modo del ciclo (interactivo / automático) lo pregunta el orquestador una
  vez por sesión, se cachea en memoria de sesión y no se persiste. Cada sesión
  nueva vuelve a preguntar: es intencional para permitir que el dev elija distinto
  según el contexto de la sesión.

- El primer cambio entrega un slice acotado, no el sistema entero. El
  orquestador hace pushback activo si el dev pide "todo de una" y redirige a la
  norma de entrega incremental.
