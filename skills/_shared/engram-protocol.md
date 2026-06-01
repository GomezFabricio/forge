# Protocolo de Engram (referencia compartida)

> Convención que las skills de forge consumen para persistir señales en engram.
> No es invocable como skill — es contenido de referencia.

## Regla rectora: señales, no datos

Engram persiste **señales del proceso de desarrollo** (estado del workflow, decisiones tomadas, descubrimientos no obvios, convenciones establecidas, configuración detectada).

NO persiste **contenido completo** (READMEs, diseño.md, tareas.md, decisiones.md, ADRs, datos del dominio del proyecto). El contenido vive en filesystem (`docs/`) y se versiona con git.

### Test mental antes de persistir

Si en 3 meses busco con `mem_search`, ¿qué quiero que aparezca?

| Quiero que aparezca | NO quiero que aparezca |
|---|---|
| "Decidimos JWT sobre sessions, ver `docs/arquitectura/decisions/001-auth-jwt.md`" | El ADR completo de 50 KB pegado en SQLite |
| "Bug N+1 en `/users` se resolvió cacheando con Redis. Patrón aplicable a otros endpoints" | El diff completo del commit que lo arregló |
| "Test runner del proyecto: pytest. Coverage tool: pytest-cov" | El README.md completo de un cambio |

Si la respuesta es **contenido completo**, va a filesystem. Si es **señal puntera** (con referencia al filesystem cuando aplica), va a engram.

## División de responsabilidades

### En FILESYSTEM (contenido, audit trail real)

```
docs/
├── auditoria/
│   └── cambios/<cambio>/
│       ├── README.md             # portada del cambio
│       ├── diseño.md             # diseño técnico (estable, solo escribe /fg-design)
│       ├── tareas.md             # checklist mutable (/fg-implement tacha tareas)
│       ├── decisiones.md         # decisiones técnicas (append-only)
│       └── assets/               # opcionales (diagramas, schemas)
└── arquitectura/
    ├── overview.md           # visión general del sistema
    ├── stack.md              # tecnologías, librerías, versiones
    └── decisions/
        └── NNN-titulo.md     # ADRs completos
```

Git versiona, audita, comparte cross-team. Esto NO se duplica en engram.

### En ENGRAM (señales, cross-session)

| Topic | Tipo | Qué guarda | Propósito |
|---|---|---|---|
| `forge/<change-name>/state` | architecture | YAML chico: fase actual, próximo paso, tareas pendientes, archivos tocados, último update | Recuperación del cambio activo post-compactación |
| `forge/decision/<slug>` | decision | Qué se decidió + por qué + path al ADR si existe | Búsqueda cross-session de decisiones grandes |
| `forge/discovery/<slug>` | discovery | Gotchas, edge cases, patrones aprendidos | Aprendizajes que sobreviven al cambio puntual |
| `forge/setup/<project>` | config | Contexto inicial del proyecto detectado por `/fg-setup` (stack, layout) | Configuración cross-session del proyecto |
| `forge/testing-capabilities/<project>` | config | Test runner, coverage, integration, e2e detectados; `strict_tdd: bool` | Activa Strict TDD Mode en `/fg-implement` y `/fg-review` |
| `skill-registry` | config | Registry de skills disponibles con compact rules | Transversal a forge — sin prefijo `forge/` |

**Nota sobre el prefijo `forge/`**: temporal hasta que se decida el nombre final del producto. Si el producto se renombra, se hace un find/replace global. El uso de prefijo evita colisiones con otros workflows (ej: si el dev también usa workflows con prefijo `sdd/` u otro).

## Naming determinístico

Para señales del cambio activo:

```
title:           forge/<change-name>/<artifact-type>
topic_key:       forge/<change-name>/<artifact-type>
type:            architecture | decision | discovery | config
project:         <nombre detectado del proyecto>
scope:           project
capture_prompt:  false
```

`capture_prompt: false` se setea cuando el schema de la tool engram lo soporta. Si una versión vieja rechaza o no expone el campo, omitirlo en vez de fallar.

### Ejemplo: artifact de estado del cambio activo

```
mem_save(
  title: "forge/<change-name>/state",
  topic_key: "forge/<change-name>/state",
  type: "architecture",
  project: "<project>",
  capture_prompt: false,
  content: """
    change: <change-name>
    phase: implement
    next_step: 'continuar checklist desde tarea 3'
    files_touched:
      - src/auth/login.py
      - tests/auth/test_login.py
    last_updated: 2026-05-26T14:30:00Z
  """
)
```

Recuperación: `mem_search("forge/<change-name>/state")` → `mem_get_observation(id)` → parsear YAML → restaurar estado.

### Ejemplo: decisión técnica grande

```
mem_save(
  title: "forge/decision/auth-jwt",
  topic_key: "forge/decision/auth-jwt",
  type: "decision",
  project: "<project>",
  capture_prompt: false,
  content: """
    Decidimos JWT sobre sessions para autenticación.
    Razón: stateless permite escalar horizontalmente sin sticky sessions; el equipo tiene experiencia previa.
    ADR completo: docs/arquitectura/decisions/001-auth-jwt.md
    Cambio que la introdujo: docs/auditoria/cambios/2026-05-feat-login-usuarios/
  """
)
```

## Protocolo de recuperación (2 pasos)

```
Paso 1: mem_search(query: "<topic_key o keywords>", project: "<project>")
        → preview truncado + ID

Paso 2: mem_get_observation(id: <observation-id>)
        → contenido completo (REQUERIDO — los previews están truncados a ~300 chars)
```

Al recuperar múltiples observaciones, agrupar primero todas las searches, después todas las retrievals:

```
PASO A — SEARCH (obtener solo IDs):
  mem_search(query: "forge/<change-name>/state", ...) → guardar ID
  mem_search(query: "forge/decision/auth-jwt", ...) → guardar ID

PASO B — RETRIEVE FULL CONTENT (obligatorio):
  mem_get_observation(id: <state_id>)
  mem_get_observation(id: <decision_id>)
```

## Comportamiento de upsert

Mismo `topic_key` + `project` + `scope` → UPDATE (sobrescribe), NO INSERT.

El contenido previo se pierde — `revision_count` incrementa pero el viejo NO se guarda. Esto es **por diseño** — engram es working memory, no audit trail. Para historia de iteración usar filesystem (los artifacts del cambio en `docs/auditoria/cambios/<cambio>/` versionados con git).

### Reglas de actualización de topic

- Topics diferentes NO DEBEN sobrescribirse entre sí.
- Mismo topic evolucionando → usar mismo `topic_key` (upsert).
- Si no estás seguro de la key → usar el patrón `forge/<change-name>/<tipo>` como default para señales del cambio activo; `forge/decision/<slug>` o `forge/discovery/<slug>` para señales cross-change.

## Cuándo persistir proactivamente

Las skills llaman `mem_save` IMMEDIATAMENTE después de cualquiera de estos eventos, sin esperar a que el dev lo pida:

| Evento | Topic | Tipo |
|---|---|---|
| Decisión de arquitectura o diseño tomada | `forge/decision/<slug>` | decision |
| Convención de equipo establecida | `forge/decision/<slug>` o `forge/discovery/<slug>` | decision o pattern |
| Cambio de workflow acordado | `forge/decision/<slug>` | decision |
| Elección de tool o librería con tradeoffs | `forge/decision/<slug>` | decision |
| Bug fix con root cause no obvio | `forge/discovery/<slug>` | discovery |
| Gotcha, edge case, comportamiento inesperado | `forge/discovery/<slug>` | discovery |
| Patrón establecido (naming, estructura) | `forge/discovery/<slug>` | pattern |
| Preferencia o constraint del dev aprendida | `forge/discovery/<slug>` | preference |
| Avance en un cambio activo | `forge/<change-name>/state` | architecture |

Lo que NO se persiste como señal independiente porque ya está en filesystem:

- README.md completo de un cambio → vive en `docs/auditoria/cambios/<cambio>/README.md`.
- diseño.md completo → vive en `docs/auditoria/cambios/<cambio>/diseño.md`.
- tareas.md completo → vive en `docs/auditoria/cambios/<cambio>/tareas.md`.
- decisiones.md completo → vive en `docs/auditoria/cambios/<cambio>/decisiones.md`.
- ADRs completos → viven en `docs/arquitectura/decisions/NNN-titulo.md`.
- Apply-progress detallado por tarea → el checklist tachado vive en `tareas.md` del cambio.
- Review report completo → la sección "Cierre" del README.md tiene la síntesis.

Si una skill quiere referenciar uno de estos artifacts desde una señal de engram, usa el **path filesystem** como puntero, no el contenido.

## Cuándo buscar memoria

Ante cualquier variación de "recordá", "qué hicimos", "cómo resolvimos", o referencias a trabajo previo:
1. Llamar `mem_context` — chequea historial reciente (rápido, barato).
2. Si no se encuentra, llamar `mem_search` con keywords relevantes.
3. Si se encuentra, usar `mem_get_observation` para contenido completo no truncado.

Buscar PROACTIVAMENTE también cuando:
- Arrancás trabajo en algo que pudo haberse hecho antes.
- El dev menciona un tema del que no tenés contexto.
- El primer mensaje del dev referencia el proyecto, una feature o un problema — buscar con keywords del mensaje antes de responder.

## Cierre de sesión (obligatorio)

Antes de terminar una sesión o decir "done" / "listo", llamar `mem_session_summary`:

```
## Goal
[En qué estábamos trabajando esta sesión]

## Instructions
[Preferencias del dev o constraints descubiertos — skip si no hay]

## Discoveries
- [Hallazgos técnicos, gotchas, learnings no obvios]

## Accomplished
- [Items completados con detalles clave]

## Next Steps
- [Qué queda pendiente — para la próxima sesión]

## Relevant Files
- path/al/archivo — [qué hace o qué cambió]
```

Esto NO es opcional. Si se salta, la próxima sesión arranca a ciegas.

## Después de compactación

Si aparece un mensaje de compactación o "FIRST ACTION REQUIRED":
1. INMEDIATAMENTE llamar `mem_session_summary` con el contenido del resumen compactado — persiste lo hecho antes de la compactación.
2. Llamar `mem_context` para recuperar contexto adicional de sesiones previas.
3. Recién DESPUÉS continuar trabajando.

No saltar el paso 1. Sin él, todo lo hecho antes de la compactación se pierde de memoria.
