# Contribuir a forge

Gracias por interesarte en contribuir. Este documento describe el flujo de trabajo, las convenciones de commits y el estilo de código del proyecto.

forge está en `v0.x` — pre-estable. La superficie del producto puede cambiar entre versiones menores hasta llegar a `v1.0.0`.

## Setup de desarrollo

```bash
git clone https://github.com/GomezFabricio/forge
cd forge
pipx install --editable ".[dev]" --include-deps
pytest
ruff check forge/
```

## Flujo de trabajo (Git)

forge usa **GitFlow-lite**: dos ramas long-lived (`main` y `develop`) más ramas efímeras por trabajo.

### Estructura de ramas

| Rama | Rol |
|---|---|
| `main` | Siempre release-ready. Cada commit en `main` es un release con tag `vX.Y.Z`. Protegida — solo se actualiza vía PR desde `develop` o `hotfix/*`. |
| `develop` | Default branch del repo. Branch de integración donde se mergean features mientras se acumula para el próximo release. |
| `feature/<nombre>` | Para features que ameritan varios commits. Mergean a `develop`. |
| `fix/<nombre>` | Bug fixes que mergean a `develop`. |
| `chore/<nombre>` | Tareas auxiliares (deps, configs). |
| `hotfix/<nombre>` | Fix urgente contra `main` después de un release. |

### Naming de ramas

forge usa **naming bilingüe** paralelo a la convención de commits:

- **Prefijo en inglés**: mismo set que los conventional commit types (`feature/`, `fix/`, `chore/`, `docs/`, `refactor/`, `hotfix/`, `test/`, `perf/`, `style/`, `build/`, `ci/`). Estándar de industria, compatible con tooling como `commitlint` o `conventional-pre-commit` si se agrega más adelante.
- **Subject en español, kebab-case**: legible para el equipo hispano-parlante.

Ejemplos:

```
feature/filtro-pii-pre-anthropic
fix/bootstrap-codegraph-faltante
chore/actualizar-presidio
hotfix/flag-version-cli
docs/aclarar-alcance-skills-en-readme
refactor/tdd-wizard-por-ciclo
```

**Por qué bilingüe**: el prefijo es el "lenguaje técnico universal" — un contributor externo o un tool de CI espera `feature/`, no `nueva/`. El subject es el "lenguaje del equipo" — más fluido para describir el qué del cambio en el contexto del proyecto.

### Flujo concreto

**Trabajo diario** (feature, fix, chore):

```
git checkout develop
git pull
git checkout -b feature/mi-cambio-en-espanol
# ... commits ...
git push -u origin feature/mi-cambio-en-espanol
# abrir PR feature/mi-cambio-en-espanol → develop
# squash and merge
```

**Release** (cuando `develop` tiene suficiente para una versión):

```
# abrir PR develop → main
# merge commit (NO squash — preservar historia de develop como contexto del release)
# en main: tag vX.Y.Z, publicar
```

**Hotfix** (fix urgente contra `main`):

```
git checkout main
git pull
git checkout -b hotfix/error-critico
# ... commits ...
git push -u origin hotfix/error-critico
# abrir PR hotfix/error-critico → main
# squash and merge
# en main: tag vX.Y.(Z+1)
# cherry-pick a develop si el bug existe también ahí
```

### Política de merge en PRs

- `feature → develop`: **squash and merge** (un commit limpio por feature en `develop`).
- `develop → main`: **merge commit** (preserva la historia de commits de develop como contexto del release).
- `hotfix → main`: **squash and merge**.

## Convención de commits

forge usa **Conventional Commits** con type en inglés y subject en español.

### Estructura

```
<type>(<scope>): <subject>

<body opcional>

<footer opcional>
```

### Types permitidos

| Type | Cuándo usarlo |
|---|---|
| `feat` | Nueva feature visible al dev. |
| `fix` | Bug fix. |
| `docs` | Solo documentación. |
| `refactor` | Cambio de código sin cambiar comportamiento. |
| `test` | Agregar o corregir tests. |
| `chore` | Tareas auxiliares (deps, configs, packaging). |
| `perf` | Mejora de performance medible. |
| `style` | Formato, espacios — sin cambio de lógica. |
| `build` | Cambios en sistema de build, `pyproject.toml`, packaging. |
| `ci` | Cambios en CI/CD. |
| `revert` | Revert de un commit anterior (con `Reverts: <hash>` en footer). |

### Scopes (opcional pero recomendado)

| Scope | Cubre |
|---|---|
| `filters` | El filtro PII pre-Anthropic (`forge/filters/`). |
| `bootstrap` | `forge/bootstrap.py` (lógica de `/fg-setup`). |
| `cli` | `forge/cli.py` (entry point del binario `forge`). |
| `hooks` | Hooks de Claude Code que forge instala. |
| `skills` | Las 6 skills (`/fg-*`). |
| `agents` | Los 6 sub-agentes especialistas. |
| `templates` | Templates de `templates/` (CLAUDE-md-institucional, etc.). |
| `config` | YAMLs per-project. |
| `deps` | Dependencias en `pyproject.toml`. |
| `release` | Bumps de versión + tag. |

Sin scope si el cambio cruza varias capas o es global del repo.

### Subject (la primera línea)

- **Idioma**: español. (Type en inglés, subject en español.)
- **Modo imperativo o presente neutro**: `agregar`, `corregir`, `eliminar`, `actualizar` — NO `agregado` ni `agrega`.
- **Sin mayúscula inicial** después de los dos puntos.
- **Sin punto final**.
- **Max 72 chars** total del header (`type(scope): subject`).
- **No describe el cómo, describe el qué**.

### Body (cuando aplica)

Obligatorio en commits no triviales. Vacío para fixes de typo o cambios mecánicos.

- Separado del subject por línea en blanco.
- Explica el **por qué**, no el **cómo** (el qué ya está en el subject, el cómo está en el diff).
- Max ~72 chars por línea.
- Puede usar bullets con `-`.

### Footer (cuando aplica)

```
Refs: #123
Closes: #456
BREAKING CHANGE: <descripción>
Reverts: <hash>
```

### Breaking changes

Marca con `!` en el header (`feat(filters)!: ...`) y/o footer `BREAKING CHANGE: <descripción>`. Preferir ambas si el cambio es grande.

### Prohibido

- `Co-Authored-By` en commits.
- Emoji / Gitmoji.
- Mensajes vacíos: `wip`, `fix`, `cambios`, `más cosas`.
- Commits mezclando temas distintos (un commit = una unidad lógica revisable).
- Tests separados del feat — en TDD strict los tests van en el mismo commit que el feat que los pasa, o en un commit RED previo si se prefiere mostrar el ciclo.

### Ejemplos

```
feat(filters): implementar CuitRecognizer con validator del dígito verificador

Pasa los tests rojos del commit anterior. Validator usa la fórmula
estándar AFIP (suma ponderada con pesos [5,4,3,2,7,6,5,4,3,2],
check = 11 - (sum % 11), casos especiales 10→9 y 11→0).
```

```
fix(bootstrap): manejar el caso de CodeGraph binario no encontrado en PATH

Antes lanzaba excepción no capturada cuando codegraph faltaba. Ahora
emite warning estructurado y continúa con detección degradada.

Closes: #12
```

```
chore(deps): agregar presidio-analyzer y presidio-anonymizer

Dependencias del filtro PII pre-Anthropic. Modo pattern-only (sin spaCy).
```

## Strict TDD

forge se construye con **Strict TDD** como auto-disciplina interna. Las tres leyes aplican:

1. NO escribir código de producción sin un test fallando.
2. NO escribir más test que el necesario para fallar.
3. NO escribir más código que el necesario para pasar.

Para cada feature, escribir al menos 2 test cases con datos distintos (triangulación obligatoria) antes de implementar.

## Estilo de código

- **Ruff** valida formato y reglas básicas (`ruff check forge/`). Configuración en `pyproject.toml`.
- **Line length**: 100 caracteres.
- **Target**: Python 3.10+.
- **Imports**: ordenados por `isort` (incluido en ruff).

## Reportar bugs o proponer mejoras

[Issues del repo](https://github.com/GomezFabricio/forge/issues).

Para reportar un bug, incluir:

- Versión de forge (`forge --version`).
- Sistema operativo y versión de Python.
- Pasos para reproducir.
- Output esperado vs output real.

## Licencia

Al contribuir aceptás que tu código se distribuye bajo la [licencia MIT](LICENSE) del proyecto.
