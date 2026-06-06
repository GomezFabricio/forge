# Guía de uso de forge

forge es un workflow de Spec-Driven Development que se instala una vez por máquina y
queda latente en Claude Code. A partir de ahí no hay nada que activar: el orquestador
detecta la intención del dev en lenguaje natural y arranca el flujo correspondiente
solo. Los comandos `/fg-*` existen para uso manual avanzado, no son el camino
principal.

---

## Contenido

1. [Modelo latente — cómo funciona forge](#1-modelo-latente)
2. [Instalación (una vez por máquina)](#2-instalación)
3. [Guía por escenario](#3-guía-por-escenario)
4. [Niveles de ceremonia](#4-niveles-de-ceremonia)
5. [Referencia de config.yaml](#5-referencia-de-configyaml)
6. [Capa PII y #fg-pass](#6-capa-pii-y-fg-pass)
7. [Comandos manuales (`/fg-*`)](#7-comandos-manuales-fg-)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Modelo latente

forge no se activa ni se desactiva: está siempre presente desde que se instaló en
`~/.claude/`. Cuando el dev le describe algo a Claude, el orquestador lee la intención
y decide si forge debe entrar o no.

### Cuándo forge entra

| Lo que el dev le dice a Claude | Lo que forge hace |
|---|---|
| "quiero hacer un sistema de X" (directorio sin proyecto) | Inicializa el proyecto (modo bootstrap), conversa para capturar la visión, genera `overview.md` + `stack.md`, y arranca el ciclo de planificación. |
| "implementá esto según docs/prd.md" | Inicializa (bootstrap), lee el documento PRD como contexto primario, y guía el cambio slice por slice desde ahí. |
| "agregame [feature] al sistema" | Adopta forge en el proyecto existente, analiza el código con CodeGraph, y planifica el cambio minimizando impacto. |
| "modificá o refactorizá este legacy" | Adopta forge, activa el análisis de impacto legacy con CodeGraph, y propone estrategia de migración antes de tocar código. |

### Cuándo forge NO entra

- Fix de typo, un ajuste de comentario, o cambio de una línea.
- Exploración o preguntas sin modificar código.
- El dev escribe explícitamente "sin forge" o "edición libre".

### El ciclo completo (referencia rápida)

```
Setup del proyecto (una vez):   /fg-setup
Por cada cambio:                 /fg-plan → /fg-design → /fg-implement → /fg-review
Mantenimiento de arquitectura:  /fg-update-arch  (sugerida por /fg-review)
```

Cada cambio genera una carpeta de auditoría en `docs/auditoria/cambios/<YYYY-MM-tipo-nombre>/`.

---

## 2. Instalación

La instalación es una sola vez por máquina. Deposita las skills, los sub-agentes y el
hook PII en `~/.claude/`, y mergea la regla de orquestación en `~/.claude/CLAUDE.md`.
Después de eso, forge funciona en cualquier proyecto sin pasos adicionales.

### Via institucional (funcional hoy)

```bash
git clone https://github.com/GomezFabricio/forge
cd forge
pipx install --editable . --include-deps
forge install
```

> Los scripts `install.sh` (Linux/Mac) e `install.ps1` (Windows) están pendientes de
> implementación. La vía funcional hoy es el clon + pipx.

**Requisitos previos:**

| Requisito | Notas |
|---|---|
| Python 3.10+ | El instalador verifica la versión. |
| Claude Code | El runtime donde corren las skills. |
| pipx | El instalador lo instala si no está. |
| CodeGraph | Opcional pero muy recomendado. Analiza código 100% local, sin enviar nada a la nube. |

### Qué instala `forge install`

| Destino en `~/.claude/` | Contenido |
|---|---|
| `skills/<stem>/SKILL.md` | Las 6 skills del workflow (`fg-setup`, `fg-plan`, `fg-design`, `fg-implement`, `fg-review`, `fg-update-arch`). |
| `skills/forge-shared/<name>/SKILL.md` | Referencias compartidas (`skill-resolver`, `engram-protocol`, `fg-phase-common`). |
| `skills/fg-implement/strict-tdd.md` | Módulo del ciclo Strict TDD. |
| `skills/fg-review/strict-tdd-verify.md` | Módulo de validación TDD para `/fg-review`. |
| `agents/<name>.md` | Los 6 sub-agentes especialistas. |
| `mcp/engram.json` | Registro MCP de engram (si se instala engram). |
| `CLAUDE.md` | Regla de orquestación mergeada (bloque `forge:orchestrator`). |

### Registro manual del hook PII

Hasta que `forge install` registre el hook automáticamente, agregarlo en
`~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python -m forge.filters.hook_user_prompt"
          }
        ]
      }
    ]
  }
}
```

---

## 3. Guía por escenario

### Escenario 1 — Greenfield sin docs

**Cuándo aplica:** directorio nuevo, sin código, sin PRD.

**Lo que el dev dice:**

> "Quiero construir un sistema de gestión de turnos médicos."

**Lo que forge hace:**

1. Detecta que no hay `.forge/` ni manifiestos → corre `/fg-setup` en modo `bootstrap`.
2. Conversa con el dev para capturar la visión (qué es el sistema, quién lo usa, stack,
   módulos principales).
3. Genera `docs/arquitectura/overview.md` y `stack.md` con lo que el dev mencionó —
   sin inventar nada.
4. Arranca `/fg-plan` iterativo para el primer cambio.

**Archivos que genera `/fg-setup` en el proyecto:**

```
CLAUDE.md
docs/auditoria/config.yaml
config/modulos-transversales.yaml
.atl/skill-registry.md
.gitignore  (actualizado)
```

**Después del setup, para cada feature:**

> "Implementá el módulo de login de pacientes."

forge arranca `/fg-plan`, infiere tipo `feat` y nombre `login-pacientes`, genera la
carpeta `docs/auditoria/cambios/2026-06-feat-login-pacientes/` con el `README.md`
inicial, y sigue con el ciclo.

---

### Escenario 2 — Greenfield con PRD

**Cuándo aplica:** directorio nuevo con un documento de producto o spec ya existente.

**Lo que el dev dice:**

> "Implementá esto según docs/prd.md."

**Lo que forge hace:**

1. Corre `/fg-setup` en modo `bootstrap` si el directorio no tiene `.git/` ni manifiestos
   (idéntico al escenario 1); si ya es un repo con manifiesto, entra en modo `adopt`, pero
   la ingesta del documento es la misma.
2. Lee `docs/prd.md` como contexto primario del cambio.
3. Si existe `docs/arquitectura/overview.md`, lo usa como contexto secundario y anota
   coincidencias o divergencias.
4. Arranca `/fg-plan --from docs/prd.md` iterativo.

**Diferencia clave vs Escenario 1:** el contexto viene del documento, no de una
conversación de visión. Si el doc apuntado no existe o está vacío, forge bloquea con
`status: blocked` y lo informa.

---

### Escenario 3 — Sistema existente (nueva feature o fix)

**Cuándo aplica:** proyecto con código y git ya inicializados.

**Lo que el dev dice:**

> "Agregame paginación al listado de expedientes."

**Lo que forge hace:**

1. Detecta `.git/` o manifiestos → corre `/fg-setup` en modo `adopt` (si no está ya
   inicializado).
2. Detecta el stack y el test runner automáticamente.
3. Arranca `/fg-plan`, usa CodeGraph para identificar archivos afectados reales.
4. Sigue el ciclo estándar: design → implement → review.

**`/fg-setup adopt` genera en el proyecto:**

```
CLAUDE.md                         (creado o mergeado)
docs/auditoria/config.yaml        (creado con stack detectado)
config/modulos-transversales.yaml (creado)
.atl/skill-registry.md            (creado)
.gitignore                        (actualizado)
```

No toca `src/`, tests, ni ningún otro archivo del proyecto.

---

### Escenario 4 — Proyecto legacy

**Cuándo aplica:** sistema con código heredado, acoplamientos ocultos, o compliance
estricto.

**Lo que el dev dice:**

> "Necesito refactorizar el módulo de facturación."

**Lo que forge hace:**

1. Corre `/fg-setup adopt` y marca el proyecto como legacy (`context.is_legacy: true`
   en `config.yaml`, o `legacy: true` en el frontmatter de `overview.md`).
2. En `/fg-plan`, el orquestador propone modo Completo (los refactors siempre van a
   Completo).
3. En `/fg-design`, antes de definir el enfoque técnico, invoca automáticamente el
   sub-agente `legacy-impact-analyzer` con CodeGraph para mapear:
   - Dependencias ocultas del módulo de facturación.
   - Consumidores del código que van a romperse.
   - Breaking changes downstream.
4. Si hay issues críticos, presenta una tabla y fuerza elegir estrategia de migración
   (Strangler Fig, Branch by Abstraction, Parallel Run, o No-touch).
5. La estrategia elegida queda registrada en `decisiones.md`.

**Para marcar un proyecto como legacy:**

```yaml
# docs/auditoria/config.yaml
context:
  is_legacy: true
```

O agregar frontmatter `legacy: true` al inicio de `docs/arquitectura/overview.md`.

---

## 4. Niveles de ceremonia

El orquestador evalúa cada cambio antes de arrancar y propone el nivel de ritual mínimo
adecuado aplicando las reglas de gradación que forge instala en el CLAUDE.md institucional.
El dev confirma o ajusta; forge nunca impone el nivel sin consentimiento (salvo `ceremonial_threshold: full`).

### Los tres niveles

| Nivel | Flujo | Cuándo aplica |
|---|---|---|
| **Libre** | forge no entra. Sin carpeta de cambio, sin ciclo. | Typo, una línea, pregunta, o el dev escribe `--libre`. |
| **Rápido** | `/fg-plan` → `/fg-implement` → `/fg-review`. Salta `/fg-design`; genera `tareas.md` desde un template reducido. | Cambio chico, tipo ligero (`docs`/`chore`/`test`/`style`), arquitectura al día. |
| **Completo** | Plan → design → implement → review. Flujo sin saltos. | Feature nueva, refactor, palabras de escala ("migrar", "reescribir", "rediseñar"), o arquitectura desactualizada. |

### El piso innegociable

`/fg-review` **siempre corre**, en cualquier nivel y con cualquier configuración.
No es negociable, no es configurable. En modo Libre no aplica porque no hay cambio
creado.

### La condición "arquitectura al día"

Rápido solo está disponible si la arquitectura está sincronizada. El orquestador verifica
mediante Grep sobre `docs/auditoria/cambios/*/README.md`: si existe algún cambio con
`structural: true` y sin `arch_synced: true`, la arquitectura está desactualizada y el
orquestador fuerza Completo.

> **Limitación declarada:** el detector solo ve cambios que pasaron por forge y fueron
> marcados `structural`. Cambios manuales externos al repo no se detectan. "Desactualizada"
> es confiable; "al día" significa "al día hasta donde forge sabe".

### Cómo forzar un nivel manualmente

El dev puede incluir una bandera en la invocación de `/fg-plan`:

| Bandera | Nivel forzado |
|---|---|
| `--libre` o `--sin-forge` | Libre |
| `--rapido` o `--lite` | Rápido (solo si arch al día) |

Si el dev pide `--rapido` pero la arquitectura está desactualizada, o la descripción
contiene palabras de escala, el orquestador aplica Completo de todas formas e informa al dev.

> **Nota:** para forzar Completo no uses una bandera de invocación —
> configurá `ceremonial_threshold: full` en `config.yaml`. De todos modos, un tipo
> pesado (`feat`/`refactor`), las palabras de escala o una arquitectura desactualizada ya
> llevan a Completo por sí solos.

### Config de proyecto: `ceremonial_threshold`

| Valor | Comportamiento |
|---|---|
| `auto` (default) | El orquestador propone el nivel y espera confirmación del dev. |
| `lite` | Sesga hacia Rápido para tipos ligeros; `feat`/`refactor` siguen yendo a Completo. |
| `full` | Fuerza Completo siempre, sin preguntar. Para entornos de auditoría estricta. |

---

## 5. Referencia de `config.yaml`

El archivo `docs/auditoria/config.yaml` controla el comportamiento del workflow para
el proyecto. Lo genera `/fg-setup` con defaults conservadores. El equipo lo edita a
mano y lo commitea.

**Regla de idempotencia:** si el archivo ya existe, `/fg-setup` no lo sobreescribe.
Para resetear a defaults: borrar el archivo y correr `/fg-setup` de nuevo.

### Tabla completa de campos

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `context.stacks` | lista | `[]` | Stacks detectados (`Python`, `Node`, `Go`, etc.). Lo regenera `/fg-setup`. |
| `context.test_runner` | objeto | `null` | Runner detectado: `name`, `command`, `detected_from`. Lo regenera `/fg-setup`. |
| `context.last_detection` | ISO 8601 | `null` | Timestamp de la última detección automática. |
| `context.pending_detection` | bool | `true` (bootstrap) / `false` (adopt) | `true` = sin manifiestos detectados aún; forge re-detecta al próximo comando. |
| `context.vision_skipped` | bool | `false` | `true` si el dev declinó la conversación de visión en modo bootstrap. |
| `context.is_legacy` | bool | `false` | Marca el proyecto como legacy; activa `legacy-impact-analyzer` en `/fg-design`. |
| `rules.workflow.cycle_mode` | `interactive` \| `automatic` | `interactive` | Default sugerido del modo de ciclo. `/fg-plan` lo pregunta una vez por sesión; el dev puede cambiar por sesión. |
| `rules.workflow.ceremonial_threshold` | `auto` \| `lite` \| `full` | `auto` | Sesgo del orquestador para el nivel de ceremonia (ver sección 4). |
| `rules.pr_size.budget_lines` | entero | `400` | Umbral de líneas para "PR grande" en el Review Workload Forecast. |
| `rules.pr_size.suggest_split` | bool | `false` | Si sugerir partir en chained PRs cuando supera el budget. |
| `rules.pr_size.enforcement` | `off` \| `warn` \| `block` | `"off"` | Qué hace forge cuando el PR supera el budget (ver tabla abajo). |
| `rules.implement.tdd` | bool | `false` | Activa el ciclo Strict TDD en `/fg-implement`. Requiere edición manual y commit. |
| `rules.implement.test_command` | string | `""` | Comando de test para `/fg-implement`. Fallback: `context.test_runner.command`. |
| `rules.implement.max_tasks_per_batch` | entero | `20` | Máximo de tareas por batch en `/fg-implement`. Al llegar al límite, guarda progreso y avisa. |
| `rules.review.test_command` | string | `""` | Comando de test para `/fg-review`. Fallback: `rules.implement.test_command` → `context.test_runner.command`. |
| `rules.review.coverage_threshold` | entero | `0` | Cobertura mínima sobre archivos cambiados. `0` = solo reporta; `N > 0` = bloquea si algún archivo queda por debajo. |

### Modos de enforcement del PR size

| `enforcement` | Comportamiento |
|---|---|
| `off` | forge no menciona el budget. 1 issue = 1 MR sin fricción. **Default recomendado** para la mayoría de los equipos. |
| `warn` | Avisa cuando el PR supera `budget_lines` pero no bloquea. Útil para devs y freelancers que quieren visibilidad. |
| `block` | Exige documentar `size:exception` en el PR body antes de continuar si el PR supera el budget. Para equipos con presión real sobre calidad de review. |

forge nunca crea ramas ni PRs automáticamente. El forecast es información, no acción.

### Configuraciones típicas

**Quiero TDD estricto:**

```yaml
rules:
  implement:
    tdd: true
    test_command: pytest          # o npx vitest run, go test ./..., etc.
  review:
    coverage_threshold: 80        # bloquea si algún archivo cambiado queda bajo 80%
```

**Quiero ceremonia mínima (proyectos de movimiento rápido):**

```yaml
rules:
  workflow:
    ceremonial_threshold: lite
    cycle_mode: automatic
```

**Proyecto legacy con auditoría estricta:**

```yaml
context:
  is_legacy: true

rules:
  workflow:
    ceremonial_threshold: full
  pr_size:
    enforcement: block
    budget_lines: 300
```

**PRs chicos forzados (equipos con review exigente):**

```yaml
rules:
  pr_size:
    budget_lines: 200
    suggest_split: true
    enforcement: block
```

---

## 6. Capa PII y `#fg-pass`

forge incluye un hook `UserPromptSubmit` que detecta y redacta datos personales e
identificadores sensibles antes de que el prompt llegue a la API de Anthropic. El
filtro opera en modo pattern-only (sin modelos NLP), con cold start menor a 300ms en
Windows. **Fail-open:** nunca bloquea el loop de Claude Code.

### Qué detecta (22 tipos)

| Categoría | Tipos detectados |
|---|---|
| Identificadores argentinos | CUIT/CUIL (con checksum AFIP), DNI_AR, CBU |
| Secretos técnicos | JWT, AWS_ACCESS_KEY, AWS_SECRET_KEY, GITHUB_PAT, GITHUB_FINE_GRAINED, OPENAI_KEY, ANTHROPIC_KEY, SLACK_TOKEN, STRIPE_KEY, PRIVATE_KEY_BLOCK, CONNECTION_STRING_PASSWORD, BEARER_TOKEN |
| Tipos Presidio built-in | CREDIT_CARD, EMAIL_ADDRESS, IBAN_CODE, IP_ADDRESS, PHONE_NUMBER, URL, CRYPTO |

### Cómo funciona

Cada detección reemplaza el dato con un placeholder estable: `[CUIT]`, `[JWT]`,
`[AWS_ACCESS_KEY]`, etc. El prompt modificado llega a Claude en lugar del original.
El texto circundante se preserva verbatim.

### Registro de auditoría

Cada redacción y cada passthrough se registran en `.forge/auditoria-pii.jsonl`
(append-only, una línea JSON por evento). El log **nunca contiene el texto del
prompt** — solo un hash SHA-256 truncado a 16 caracteres para correlación.

### `#fg-pass` — override del filtro

Para pasar un prompt sin filtrar (fixtures de test, datos de ejemplo, debugging del
propio filtro), incluir el marcador `#fg-pass` en cualquier parte del prompt:

```
cuit_proveedor = "20-12345678-6"  #fg-pass
```

**Semántica:**

- Todo o nada: `#fg-pass` bypasea el filtro completo para ese prompt.
- Case-sensitive: solo el literal exacto `#fg-pass` activa el override.
  `#FG-PASS`, `#fg_pass`, `# fg-pass` **no** lo activan.
- Aplica solo al prompt donde aparece, no a los siguientes.
- Incluso con `#fg-pass`, el hook registra un evento `action: "passthrough"` en
  `.forge/auditoria-pii.jsonl` con el hash del prompt.

### Kill-switch

Para desactivar el filtro sin revertir código:

```bash
export FORGE_PII_DISABLE=1
```

---

## 7. Comandos manuales (`/fg-*`)

El dev no necesita estos comandos en el flujo normal — el orquestador los llama
internamente. Son útiles para automatización, scripts, re-ejecuciones puntuales o
depuración.

| Comando | Propósito |
|---|---|
| `/fg-setup` | Adopta forge en el proyecto. Idempotente: re-ejecutable para upgrade. Detecta stack, genera `config.yaml`, inicializa CodeGraph, mergea `CLAUDE.md`. |
| `/fg-plan <descripción libre>` | Crea la carpeta de cambio con el `README.md` inicial. Infiere tipo (`feat`/`fix`/`refactor`/etc.) y nombre kebab-case desde lenguaje natural. El nivel de ceremonia llega ya resuelto desde el orquestador. |
| `/fg-plan --from <doc> "<descripción>"` | Igual que `/fg-plan` pero usa un documento externo como contexto primario del cambio. |
| `/fg-design` | Genera `diseño.md`, `tareas.md` y `decisiones.md`. Requiere que `/fg-plan` ya haya corrido. En proyectos legacy, invoca `legacy-impact-analyzer` antes del enfoque técnico. |
| `/fg-implement` | Implementa el checklist de `tareas.md` tarea por tarea. Si TDD está activo, aplica el ciclo de 7 pasos. Soporta batching: corta al llegar a `max_tasks_per_batch` y guarda progreso. |
| `/fg-review` | Corre la suite completa, valida TDD Cycle Evidence (si activo), audita calidad de assertions, invoca sub-agentes especialistas según el contexto, y escribe el Cierre del `README.md`. Única skill que puede delegar. |
| `/fg-update-arch` | Reconcilia `docs/arquitectura/` con la realidad del código vía CodeGraph. Propone diffs por archivo; el dev acepta, edita o rechaza cada uno individualmente. Sugerida por `/fg-review` cuando detecta cambios estructurales. |

### Sub-agentes que `/fg-review` puede invocar

| Sub-agente | Cuándo se invoca |
|---|---|
| `code-reviewer` | Siempre. Review general estilo Senior Staff Engineer. |
| `security-reviewer` | Cuando el cambio toca auth, datos sensibles o endpoints públicos. |
| `dba-reviewer` | Cuando hay migraciones o queries pesadas. |
| `frontend-reviewer` | Cuando toca UI/UX (componentes, páginas). |
| `qa-reviewer` | Cuando hay tests complejos o de integración nuevos. |
| `legacy-impact-analyzer` | Cuando el proyecto está marcado como legacy. También en `/fg-design` para analizar impacto antes del enfoque técnico. |

### Strict TDD — el ciclo de 7 pasos

Activo cuando `rules.implement.tdd: true`. `/fg-implement` aplica este ciclo por
cada tarea:

| Paso | Descripción |
|---|---|
| SAFETY NET | Correr tests pre-existentes de archivos a modificar. Si fallan, reportar al dev y no continuar (no arreglar pre-existing failures). |
| UNDERSTAND | Releer la tarea, el diseño, el código existente y los patrones de test del proyecto. |
| RED | Escribir el test que describe el comportamiento esperado (el código de producción referenciado no existe aún). |
| GREEN | Escribir el mínimo código necesario para que el test pase. Ejecutar y confirmar. |
| TRIANGULATE | Agregar un segundo test case con inputs distintos para forzar lógica real (no return hardcodeado). Mínimo 2 test cases por tarea. |
| REFACTOR | Mejorar sin cambiar comportamiento. Ejecutar tests después de cada refactor. |
| Complete | Tachar la tarea en `tareas.md`. Anotar decisiones no anticipadas en `decisiones.md`. |

---

## 8. Troubleshooting

### forge no se activó con mi mensaje

forge entra cuando la intención es crear, modificar o implementar algo. Si el mensaje
es una pregunta, exploración, o cambio de una línea, el orquestador lo clasifica como
Libre y no entra.

Para forzar la entrada: agregar contexto que indique un cambio real, o invocar
`/fg-plan` manualmente.

### Quiero saltar forge para este cambio

Incluir "sin forge" o "edición libre" en el prompt, o usar la bandera `--libre`:

```
/fg-plan --libre arreglar typo en el README
```

### No se detectó mi stack ni test runner

El modo `bootstrap` (directorio sin manifiestos) crea el config con
`pending_detection: true`. Cuando el dev agrega los manifiestos del proyecto
(`pyproject.toml`, `package.json`, etc.), forge re-detecta automáticamente al
próximo comando.

También se puede correr `/fg-setup` de nuevo — no sobreescribe archivos existentes,
solo agrega lo que falta.

### Quiero resetear el config a los defaults

```bash
rm docs/auditoria/config.yaml
# Luego:
/fg-setup
```

`/fg-setup` es idempotente: si el archivo no existe lo crea; si existe lo preserva.

### El orquestador propone Completo pero el cambio es chico

Causas posibles:

1. Hay cambios estructurales sin sincronizar en `docs/auditoria/cambios/`. Correr
   `/fg-update-arch` para sincronizarlos, y después el orquestador va a poder proponer
   Rápido.
2. El tipo inferido del cambio es pesado (`feat`/`refactor`): estos van a Completo por
   regla conservadora, sin importar el tamaño. Si el cambio es realmente chico, declará un
   tipo ligero (`docs`/`chore`/`test`/`style`) o forzá `--rapido`.
3. La descripción contiene palabras de escala ("migrar", "reescribir", etc.) aunque el
   cambio sea chico. Reformular la descripción.

El dev siempre puede forzar `--rapido` explícitamente si la arquitectura está al día.

### La implementación se cortó antes de terminar (batching)

`/fg-implement` corta cuando llega al límite de `max_tasks_per_batch` (default: 20) y
guarda el progreso en engram. La próxima invocación retoma donde quedó.

Recomendación: correr cada batch en una sesión nueva para mantener el contexto del
modelo fresco ("1 sesión = 1 ciclo").

### Cómo verificar qué detecta el filtro PII en un prompt

```
texto_de_prueba = "CUIT: 20-12345678-6, email: dev@ejemplo.com"  #fg-pass
```

Con `#fg-pass`, el filtro no redacta el prompt pero sí registra el evento en
`.forge/auditoria-pii.jsonl`.

---

## Estructura del proyecto después de `/fg-setup`

```
mi-proyecto/
├── CLAUDE.md                         ← convenciones institucionales (mergeado)
├── config/
│   └── modulos-transversales.yaml    ← qué considera estructural el detector
├── docs/
│   ├── arquitectura/                 ← documentación permanente del sistema
│   │   ├── overview.md
│   │   ├── stack.md
│   │   └── decisions/                ← ADRs
│   └── auditoria/
│       ├── config.yaml               ← configuración del workflow forge
│       └── cambios/                  ← un cambio = una carpeta
│           └── 2026-06-feat-login/
│               ├── README.md          ← portada (humano)
│               ├── diseño.md          ← técnico estable (solo escribe /fg-design)
│               ├── tareas.md          ← checklist mutable (/fg-implement tacha)
│               ├── decisiones.md      ← decisiones técnicas (append-only)
│               └── evidencia-tdd.md   ← evidencia del ciclo TDD (solo si TDD activo)
├── .atl/
│   └── skill-registry.md             ← registry de skills del proyecto
├── .codegraph/                       ← índice de CodeGraph (gitignored)
├── .engram/                          ← memoria cross-session (gitignored salvo chunks/)
└── .forge/                           ← runtime de forge (gitignored)
```

forge no impone estructura en `src/`, tests, ni ningún otro archivo del proyecto.
