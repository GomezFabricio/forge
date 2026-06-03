# Changelog

Todas las modificaciones relevantes de **forge** quedan documentadas en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

> **Política pre-1.0**: la serie `0.x` indica "pre-estable" — la API y el comportamiento pueden cambiar sin previo aviso entre versiones menores. Se llegará a `v1.0.0` cuando el primer piloto cierre con éxito.

## [Unreleased]

### Modelo de activación latente

Implementa el PRD `.forge/prd-activacion-latente.md`: forge se vuelve latente e
invocable por intent natural en lugar de comando explícito.

### Added

- **`forge install` implementado** (`forge/installer.py`, ~270 LOC): depósito de skills, agents y registro de MCP de engram en `~/.claude/`. Incluye detección automática de engram (3 indicadores), prompt Y/N interactivo, flag `--install-engram` (non-interactive), flag `--skip-engram-check`, e idempotencia completa.
- **Auto-install de engram**: descarga el binario desde GitHub Releases (`engram_{version}_{os}_{arch}.tar.gz|.zip`), extrae el binario, aplica `chmod +x` (Unix), limpia quarantine en macOS, edita `~/.profile` (Unix) o `HKCU\Environment\Path` (Windows), y escribe `~/.claude/mcp/engram.json` con schema flat.
- **Deposit de skills con transformación de layout**: `fg-*.md` → `~/.claude/skills/<stem>/SKILL.md`; co-located companions (`strict-tdd.md`, `strict-tdd-verify.md`) depositados junto a su skill consumidora; archivos cross-cutting (`skill-resolver`, `engram-protocol`, `fg-phase-common`) → `~/.claude/skills/forge-shared/<name>/SKILL.md` con frontmatter `disable-model-invocation: true` inyectado.
- **Exit codes claros**: `EXIT_OK=0`, `EXIT_ABORTED=10`, `EXIT_ENGRAM_INSTALL_FAILED=20`, `EXIT_DEPOSIT_FAILED=30`, `EXIT_PLATFORM_UNSUPPORTED=40`.
- **Test suite** (`tests/test_installer.py`, `tests/test_cli.py`): 201 tests nuevos, cobertura ≥88% sobre `forge/installer.py` y 100% sobre `forge/cli.py` modificado. Strict TDD ciclo RED→GREEN→TRIANGULATE→REFACTOR por tarea.
- **Inyección de regla `<!-- forge:orchestrator -->`** en `~/.claude/CLAUDE.md` global desde `forge install` (#13).
- **`bootstrap.detect_mode(root)`** devuelve `bootstrap | adopt | upgrade` según estado del directorio (#16).
- **Lazy detection de stack/test_runner**: `bootstrap.needs_detection` + `bootstrap.update_detection_fields` para re-detección post-`/fg-setup` (#16).
- **GATE de lazy detection** en `_shared/fg-phase-common.md` Sección A — fuerza re-detección cuando `pending_detection: true` (#16).
- **`/fg-setup` modo bootstrap**: dispara conversación de visión del sistema y produce `docs/arquitectura/overview.md` + `stack.md` antes del primer código (#17).
- **Helpers de bootstrap para modo greenfield**: `bootstrap.create_arquitectura_docs`, `bootstrap.patch_config_stacks`, `bootstrap.mark_vision_skipped`, `bootstrap.read_overview`, `bootstrap.is_vision_skipped`, `bootstrap.is_legacy_project` (#17, #18, #19).
- **`/fg-plan` lee `overview.md`** como contexto primario via `bootstrap.read_overview` antes de consultar CodeGraph (#18).
- **`/fg-plan --from <ruta-doc>`**: ingesta de doc externa (PRD, RFC) como contexto primario para el plan (#18).
- **`/fg-design` invoca `legacy-impact-analyzer`** ANTES de definir enfoque cuando `context.is_legacy: true` (#19).
- **Campos nuevos en `config.yaml.context`**: `last_detection`, `pending_detection`, `vision_skipped`, `is_legacy` (#16, #17, #19).

### Changed

- **`forge/cli.py`**: eliminado flag `--global`; agregados `--install-engram` y `--skip-engram-check`; `cmd_install` ahora es thin dispatch a `forge.installer.run`.
- **`forge/bootstrap.py`**: agregado `TODO(forge-bootstrap-package-root)` documentando el bug de `PACKAGE_ROOT` en instalaciones wheel non-editable (sin fix en este ciclo).
- **Rename de paths a español**: `docs/audit/changes/` → `docs/auditoria/cambios/`, `docs/audit/config.yaml` → `docs/auditoria/config.yaml`, `docs/architecture/` → `docs/arquitectura/`. Todas las skills, agentes, templates y `bootstrap.py` actualizados.
- **Split de template de diseño**: `templates/design-change.md` reemplazado por tres archivos con responsabilidad exclusiva: `templates/diseño.md` (estable), `templates/tareas.md` (mutable), `templates/decisiones.md` (append-only). Mapping canónico de sub-docs por agente documentado en `/fg-review`.
- **`print_report` del installer**: ya no menciona `/fg-setup` como próximo paso — refleja modelo latente (#15).
- **README "Después de instalar"**: reescrita — forge se invoca por intent natural, no por comando (#15).
- **README "Cómo se activa forge"** (sección nueva): tabla intent → cadena de skills disparada (#15).
- **Template `CLAUDE-md-institucional.md`**: reframeado a voz "el orquestador detecta intent"; nueva sección "Visión del sistema (modo bootstrap)" (#20).
- **Regla "nunca crear `docs/arquitectura/` vacío"**: relajada en `fg-setup.md` y `fg-update-arch.md` — modo bootstrap puede crearlos antes del primer código (#17).

### Removed

- **Línea `print("  Próximo paso: /fg-setup")`** del `print_report` del installer (#15).
- **Flag `--global` del README**: ya removida del CLI en `6e4763b`, ahora también limpia en docs (#14).
- **Referencias stale a `commands/fg-*.md`** en README: la estructura de depósito no usa `commands/` (#14).

### Pendiente para próximas iteraciones

- Scripts `install.sh` (Linux/Mac) e `install.ps1` (Windows) en la raíz del repo para instalación de un solo comando.
- Integración real con CodeGraph en `forge/structural_detector.py` (hoy hay un placeholder con TODO).
- Fix de `PACKAGE_ROOT` en `bootstrap.py` para instalaciones wheel non-editable (ver TODO marcado).

## [0.1.0] — 2026-05-27

### Added

- **6 skills** del workflow SDD: `/fg-setup`, `/fg-plan`, `/fg-design`, `/fg-implement`, `/fg-review`, `/fg-update-arch`.
- **6 sub-agentes** especialistas de review: `code-reviewer`, `security-reviewer`, `dba-reviewer`, `frontend-reviewer`, `qa-reviewer`, `legacy-impact-analyzer`. Solo `/fg-review` puede delegar a ellos.
- **Bootstrap por proyecto** (`forge/bootstrap.py`, invocado por `/fg-setup`): detecta stack, identifica test runner, activa Strict TDD si corresponde, mergea `CLAUDE.md` institucional, inicializa CodeGraph, configura `.gitignore`.
- **Detector de cambios estructurales** (`forge/structural_detector.py`, invocado por `/fg-review`): aplica 4 heurísticas en paralelo (manifiestos, módulos transversales, migraciones de BD, módulos top-level nuevos vía CodeGraph) y marca cambios como `structural: true` para disparar `/fg-update-arch`.
- **Configuración per-project** (en `<proyecto>/config/`): `modulos-transversales.yaml` (qué considera estructural el detector). Lleva un bloque didáctico al tope explicando qué hace, cómo se usa y cómo ajustarlo.
- **Privacidad de engram por disciplina del agente**: el `CLAUDE.md` institucional que `/fg-setup` mergea incluye la regla operativa "engram persiste señales del proceso, no datos del dominio". No hay scrubber automático — la barrera es la disciplina del agente reforzada por el system prompt.
- **Strict TDD Mode + Triangulación** heredados como módulo compartido (`skills/_shared/strict-tdd.md` y `strict-tdd-verify.md`): ciclo de 7 pasos por tarea, triangulación obligatoria, banned assertion patterns auditados por `/fg-review`.
- **Persona del orquestador** "mentor cordial con rigor profesional" con 10 reglas no negociables, en español.
- **Convención de cambios**: un cambio = una carpeta `docs/audit/changes/<YYYY-MM-tipo-nombre>/` con `README.md` (portada humano) + `design.md` (técnico vivo). Sin Envelope JSON estricto.
- **Idioma**: artefactos al dev en español; identificadores de código, conventional types y nombres de tools/MCPs/hooks en inglés.
- **Licencia MIT**.

### Notes

Esta es la primera versión publicada. El producto es **pre-estable** — pueden haber cambios incompatibles entre `0.x.y` y `0.x.z`. Usar en entornos productivos críticos solo después de validación local.

[Unreleased]: https://github.com/GomezFabricio/forge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/GomezFabricio/forge/releases/tag/v0.1.0
