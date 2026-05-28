# Changelog

Todas las modificaciones relevantes de **forge** quedan documentadas en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

> **Política pre-1.0**: la serie `0.x` indica "pre-estable" — la API y el comportamiento pueden cambiar sin previo aviso entre versiones menores. Se llegará a `v1.0.0` cuando el primer piloto cierre con éxito.

## [Unreleased]

### Pendiente para próximas iteraciones

- Implementación real del subcomando `forge install --global` (deposita skills, agents y commands en `~/.claude/`).
- Scripts `install.sh` (Linux/Mac) e `install.ps1` (Windows) en la raíz del repo para instalación de un solo comando.
- Integración real con CodeGraph en `forge/structural_detector.py` (hoy hay un placeholder con TODO).
- Suite de tests `pytest` para `bootstrap.py`, `structural_detector.py` y el CLI.

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
