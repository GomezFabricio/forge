# forge

> Workflow de **Spec-Driven Development** para Claude Code, pensado para entornos críticos: privacidad rigurosa de datos sensibles, auditoría trazable de cada decisión asistida por IA, y permisos estrictos por defecto.

[![Versión](https://img.shields.io/badge/versión-0.1.0-blue.svg)](https://github.com/GomezFabricio/forge/releases)
[![Licencia](https://img.shields.io/badge/licencia-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

> **Estado**: `v0.1.0` — pre-estable. La API y el comportamiento pueden cambiar entre versiones menores. Usar en producción crítica solo después de validación local.

---

## Qué es forge

**forge** es una herramienta que se instala como skills, hooks y sub-agentes dentro de Claude Code, y aporta un workflow estructurado de SDD pensado para equipos que trabajan en entornos sensibles (sector público, salud, finanzas, sistemas legacy con compliance estricto).

Los tres ejes que el producto endurece sobre la operación habitual de Claude Code:

1. **Privacidad** — la regla operativa "engram persiste señales del proceso, no datos del dominio" está incorporada al `CLAUDE.md` institucional que `/fg-setup` mergea. La disciplina del agente es la barrera principal contra que identificadores y secretos del dominio terminen en memoria persistente.
2. **Auditoría** — cada cambio queda registrado en `docs/audit/changes/<cambio>/` con un `README.md` (portada humano) y un `design.md` (técnico vivo). El historial de git es la cadena de auditoría.
3. **Permisos estrictos** — el agente no ejecuta acciones destructivas sin autorización explícita. Configuración `bypassPermissions: false` por defecto.

forge **no reemplaza** Claude Code — vive encima de él, agregando las skills, hooks y sub-agentes que el workflow necesita.

---

## Instalación

### Vía rápida (devs personales, equipos abiertos)

**Linux / Mac**:

```bash
curl -sSL https://github.com/GomezFabricio/forge/raw/main/install.sh | bash
```

**Windows (PowerShell)**:

```powershell
iwr https://github.com/GomezFabricio/forge/raw/main/install.ps1 -useb | iex
```

### Vía institucional (entornos con compliance estricto)

Para equipos con políticas que no permiten ejecutar scripts remotos sin auditoría previa:

```bash
git clone https://github.com/GomezFabricio/forge
cd forge
make install
```

El comando `make install` invoca el mismo `install.sh` localmente — el dev puede revisar el código antes de ejecutar.

### Qué hace el instalador

Ambas vías ejecutan los siguientes pasos en cadena:

1. Verifica que haya **Python 3.10+** disponible. Si no encuentra `pipx`, lo instala (`python -m pip install --user pipx` + `pipx ensurepath`).
2. Instala el paquete con **pipx**: `pipx install forge`. Esto aísla forge del Python global del sistema y permite upgrade/uninstall limpios.
3. Ejecuta **`forge install --global`**, que deposita en `~/.claude/`:
   - `skills/forge/fg-*.md` — las 6 skills del workflow.
   - `agents/forge-*.md` — los 6 sub-agentes especialistas.
   - `commands/fg-*.md` — los slash commands correspondientes.
   - `skills/forge-shared/` — referencias compartidas (skill-resolver, persistence-contract, módulo Strict TDD).

> **v0.1.0**: el subcomando `forge install --global` está esqueletado pero no implementado en esta primera versión. Mientras tanto, los archivos del paquete se pueden copiar manualmente a `~/.claude/` para probar el workflow.

### Después de instalar

En cada proyecto donde quieras adoptar el workflow:

```bash
cd mi-proyecto/
# desde Claude Code:
/fg-setup
```

`/fg-setup` adopta forge en el proyecto — detecta stack, activa Strict TDD si hay test runner, mergea un `CLAUDE.md` institucional con las reglas del workflow (incluida la regla operativa de privacidad para engram).

---

## Workflow

Un cambio en forge sigue 4 fases por defecto, más una skill de mantenimiento de arquitectura:

```
Setup del proyecto (una vez):  /fg-setup
Por cada cambio:               /fg-plan → /fg-design → /fg-implement → /fg-review
Mantenimiento arquitectura:    /fg-update-arch  (sugerida por /fg-review)
```

### Las 6 skills

| Skill | Propósito |
|---|---|
| `/fg-setup` | Adopta forge en el proyecto. Idempotente, re-invocable para upgrade. |
| `/fg-plan <descripción libre>` | Crea la carpeta `docs/audit/changes/<YYYY-MM-tipo-nombre>/` con el `README.md` inicial. Infiere `tipo` (feat/fix/refactor/...) y `nombre` desde el lenguaje natural. |
| `/fg-design` | Llena el `design.md` con archivos afectados (vía CodeGraph), decisiones técnicas y checklist de tareas. |
| `/fg-implement` | Implementa el checklist tarea por tarea aplicando el ciclo Strict TDD si está activo (Safety Net → Understand → RED → GREEN → TRIANGULATE → REFACTOR). |
| `/fg-review` | Corre la suite completa, valida TDD Cycle Evidence, audita assertion quality, delega a sub-agentes especialistas según el cambio, y consolida el cierre. Única skill que delega. |
| `/fg-update-arch` | Reconcilia la documentación permanente del proyecto (`docs/architecture/`) con la realidad del código. Propone diff por archivo, nunca todo-o-nada. |

### Estructura de docs por cambio

```
docs/
├── architecture/                ← documentación permanente (gestionada por /fg-update-arch)
│   ├── overview.md
│   ├── stack.md
│   └── decisions/               ← ADRs
└── audit/                       ← cadena de auditoría IA-asistida
    └── changes/
        └── 2026-05-feat-login/  ← un cambio
            ├── README.md        ← portada (lectura humano)
            ├── design.md        ← técnico vivo (checklist, decisiones, archivos)
            └── assets/          ← opcional
```

---

## Sub-agentes especialistas

`/fg-review` delega a sub-agentes según el contexto del cambio. Cada uno aporta una mirada especializada al envelope final:

| Sub-agente | Cuándo se invoca |
|---|---|
| `code-reviewer` | Siempre. Review general estilo Senior Staff Engineer. |
| `security-reviewer` | Cuando el cambio toca auth, datos sensibles o endpoints públicos. |
| `dba-reviewer` | Cuando hay migraciones o queries pesadas. |
| `frontend-reviewer` | Cuando toca UI/UX (componentes, páginas). |
| `qa-reviewer` | Cuando hay tests complejos o de integración nuevos. |
| `legacy-impact-analyzer` | Cuando el proyecto está marcado como legacy. Mapea acoplamientos ocultos con CodeGraph. |

Las demás skills (`/fg-setup`, `/fg-plan`, `/fg-design`, `/fg-implement`, `/fg-update-arch`) son **ejecutores estrictos** — no delegan. Solo `/fg-review` puede invocar sub-agentes.

---

## Configuración por proyecto

Después de correr `/fg-setup`, el proyecto tiene un archivo editable en `config/`:

### `config/modulos-transversales.yaml`

Le indica al detector de cambios estructurales qué paths del proyecto son **transversales** — es decir, su modificación impacta varias áreas y debe disparar `/fg-update-arch`.

Ejemplos comentados típicos: `src/auth/`, `src/db/`, `src/logging/`, `src/middleware/`, `src/i18n/`. Descomentar los que apliquen a tu proyecto.

---

## Strict TDD Mode

forge soporta un ciclo Strict TDD opt-in. Está OFF por default — `/fg-setup` no lo activa, lo decide el equipo editando el archivo de configuración del proyecto.

**Activarlo**: editar `docs/audit/config.yaml` y cambiar `rules.implement.tdd` a `true`. El cambio queda versionado.

Cuando está activo:

- `/fg-implement` aplica el ciclo de 7 pasos por tarea: **Safety Net → Understand → RED → GREEN → TRIANGULATE → REFACTOR → Complete**.
- Las tres leyes se respetan: (1) no escribir producción sin test fallando, (2) no escribir más test que el necesario para fallar, (3) no escribir más código que el necesario para pasar.
- `/fg-review` audita assertion quality (tautologías, ghost loops, smoke tests, mock-heavy tests son flaggeados como WARNING o CRITICAL según severidad) y opcionalmente valida cobertura mínima (`rules.review.coverage_threshold`).

Cuando está OFF, `/fg-implement` opera en modo estándar y `/fg-review` aplica validación básica.

### Modo del ciclo SDD (interactivo / automático)

Independiente del TDD, el **modo de ejecución del ciclo** lo decide el dev al arrancar el primer ciclo de la sesión:

- **Interactivo**: cada fase pausa al cerrar y espera confirmación del dev para seguir.
- **Automático**: las fases se encadenan sin pausa hasta el final del ciclo.

La elección se cachea para la sesión actual — `/fg-plan` pregunta una sola vez por sesión y reusa la respuesta para los ciclos siguientes. Sesión nueva → vuelve a preguntar. El cache no se persiste en filesystem.

---

## CodeGraph

forge integra [CodeGraph](https://github.com/colbymchenry/codegraph) (MIT, 100% local, 19 lenguajes) como herramienta oficial de análisis estructural del código. `/fg-setup` lo inicializa por proyecto.

CodeGraph se usa para:

- `/fg-plan` → identificar contexto del cambio sin grep ciego.
- `/fg-design` → llenar la sección "Archivos afectados" del `design.md`.
- `/fg-review` → detectar módulos top-level nuevos y cambios en dependencias.
- `/fg-update-arch` → reconciliar topología del código con la documentación.

Si CodeGraph no está disponible, forge sigue funcionando degradado (los detectores caen a heurísticas de paths).

---

## Idioma

forge habla **español al dev**: mensajes, reportes, comentarios de los YAMLs, secciones del `CLAUDE.md` institucional, todos los artefactos generados.

Los **identificadores técnicos** (nombres de comandos, slash commands, hooks, tipos, conventional types como `feat`/`fix`/`refactor`) quedan en **inglés** porque son estándar transversal del ecosistema.

---

## Requisitos

- **Python 3.10+** (para el paquete y los hooks).
- **Claude Code** (el runtime agentic donde corren las skills).
- **CodeGraph** opcional pero muy recomendado (analiza el código local sin enviar nada a la nube).
- **pipx** para instalación aislada (el instalador lo instala si no está).

---

## Estructura del repo (source)

> Esta es la estructura del repo `forge` (source). **`forge install --global` distribuye estos archivos a `~/.claude/`** — el dev que adopta forge no necesita tener `skills/`, `agents/` ni `templates/` en su proyecto. La estructura del proyecto del dev tras `/fg-setup` se muestra más abajo.

```
forge/
├── forge/                       ← paquete Python instalable
│   ├── __init__.py
│   ├── cli.py                   ← entry point del binario `forge`
│   ├── bootstrap.py             ← ejecutor de /fg-setup (instala forge en un proyecto)
│   └── structural_detector.py   ← detector usado por /fg-review
├── skills/                      ← 6 skills + módulos compartidos (van a ~/.claude/skills/forge/)
│   ├── fg-setup.md
│   ├── fg-plan.md
│   ├── fg-design.md
│   ├── fg-implement.md
│   ├── fg-review.md
│   ├── fg-update-arch.md
│   └── _shared/                 ← skill-resolver, persistence-contract, strict-tdd
├── agents/                      ← 6 sub-agentes especialistas (van a ~/.claude/agents/)
│   ├── code-reviewer.md
│   ├── security-reviewer.md
│   ├── dba-reviewer.md
│   ├── frontend-reviewer.md
│   ├── qa-reviewer.md
│   └── legacy-impact-analyzer.md
├── config/                      ← template de configuración per-project (se copia al proyecto)
│   └── modulos-transversales.yaml
├── templates/                   ← templates de artefactos generados (se aplican al proyecto)
│   ├── README-change.md
│   ├── design-change.md
│   └── CLAUDE-md-institucional.md
├── docs/                        ← documentación interna del paquete
│   ├── herencias.md
│   └── codegraph-integration.md
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
└── .gitignore
```

## Estructura del proyecto del dev después de `/fg-setup`

Después de correr `/fg-setup` en un proyecto, forge crea o mergea **solo** lo siguiente. Las skills, agents y templates **no se copian** al proyecto — viven globalmente en `~/.claude/` y se descubren desde ahí.

```
mi-proyecto/
├── CLAUDE.md                    ← convenciones institucionales (mergeado por /fg-setup)
├── config/
│   └── modulos-transversales.yaml   ← qué considera estructural el detector
├── docs/
│   └── audit/                   ← cadena de auditoría IA-asistida
│       ├── index.md
│       └── changes/             ← un cambio = una carpeta
│           └── 2026-05-feat-login/
│               ├── README.md    ← portada (lectura humano)
│               └── design.md    ← técnico vivo
├── .atl/
│   └── skill-registry.md        ← registry de skills resueltas para este proyecto
├── .codegraph/                  ← índice de CodeGraph (gitignored)
├── .engram/                     ← memoria persistente cross-session (gitignored salvo chunks/)
├── .forge/                      ← runtime de forge (gitignored)
└── .gitignore                   ← actualizado con las entradas necesarias
```

El resto del proyecto (`src/`, tests, build configs, etc.) lo administra el dev — forge no impone arquitectura.

---

## Contribuir

forge está en pre-estable (`0.x`). Las contribuciones son bienvenidas pero la superficie del producto puede cambiar entre versiones menores hasta llegar a `v1.0.0`.

Para reportar bugs o proponer mejoras: [issues del repo](https://github.com/GomezFabricio/forge/issues).

Para contribuir código:

1. Fork del repo.
2. `pipx install --editable . --include-deps` para desarrollo local.
3. `pytest` debe pasar.
4. `ruff check forge/` debe pasar limpio.
5. Pull request con descripción clara del cambio.

---

## Licencia

[MIT](LICENSE). Copyright (c) 2026 Fabricio Gomez.
