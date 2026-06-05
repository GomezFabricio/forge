#!/usr/bin/env python3
"""Detector de cambios estructurales para forge.

Usado por /fg-review para decidir si marcar un cambio como `structural: true` y
sugerir /fg-update-arch al cerrar.

Inputs:
    - changed_files: lista de paths modificados en el cambio (relativos al root).
    - (opcional) git_rev_a, git_rev_b: aceptados por compatibilidad de API pero no
      usados internamente (ADR-3: CodeGraph no compara revisiones).

Output: dict con `is_structural`, `signals`, `details`.

Heurísticas (cualquiera de estas marca el cambio como estructural):
    1. Toca archivos de manifiesto (requirements.txt, package.json, go.mod, etc.).
    2. Toca paths declarados como transversales en config/modulos-transversales.yaml.
    3. Toca archivos de migración de BD.
    4. CodeGraph detecta módulos top-level nuevos confirmados en el índice actual
       que aparecen entre los changed_files (estrategia híbrida git+codegraph).

Si CodeGraph no está instalado o no está disponible, el detector se apoya solo
en heurísticas de paths (fallback graceful — sin excepción).

Estrategia de detección de módulos top-level (ADR-2):
    - git/paths aportan el eje temporal: qué archivos cambiaron.
    - CodeGraph confirma la realidad estructural: qué top-levels tienen símbolos reales.
    - Se usan en combinación: candidatos de changed_files ∩ módulos confirmados por codegraph.

Nota sobre rev_a/rev_b (ADR-1, ADR-3):
    CodeGraph opera siempre sobre el índice actual; no acepta parámetros de revisión.
    La comparación temporal es responsabilidad de git (changed_files).
    rev_a/rev_b se mantienen en detect() por compatibilidad de API con main() y callers
    externos, pero no se propagan al detector real.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("structural_detector: pyyaml no instalado.\n")
    sys.exit(1)


DEFAULTS = {
    "transversal_paths": [],
    "manifest_files": [
        "requirements.txt", "pyproject.toml", "package.json", "package-lock.json",
        "go.mod", "go.sum", "Cargo.toml", "composer.json", "pom.xml", "build.gradle",
        "Gemfile", "Gemfile.lock",
    ],
    "migration_paths": [
        "migrations/", "db/migrate/", "alembic/versions/", "prisma/migrations/",
        "app/db/migrations/",
    ],
}


def project_root() -> Path:
    """Heurística: subir desde cwd hasta encontrar .git o .codegraph; fallback a cwd."""
    here = Path.cwd().resolve()
    for path in [here, *here.parents]:
        if (path / ".git").exists() or (path / ".codegraph").exists():
            return path
    return here


def load_config(root: Path) -> dict:
    config_path = root / "config" / "modulos-transversales.yaml"
    if not config_path.exists():
        return DEFAULTS.copy()
    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {
            "transversal_paths": data.get("transversal_paths") or DEFAULTS["transversal_paths"],
            "manifest_files": data.get("manifest_files") or DEFAULTS["manifest_files"],
            "migration_paths": data.get("migration_paths") or DEFAULTS["migration_paths"],
        }
    except (yaml.YAMLError, OSError):
        return DEFAULTS.copy()


def normalize_path(p: str) -> str:
    return str(p).replace("\\", "/")


def is_manifest(path: str, manifest_files: list) -> bool:
    name = Path(path).name
    return name in manifest_files


def is_under_path(file_path: str, prefixes: list) -> bool:
    norm = normalize_path(file_path)
    return any(norm == p.rstrip("/") or norm.startswith(p) for p in prefixes)


def codegraph_available(root: Path) -> bool:
    if not shutil.which("codegraph"):
        return False
    return (root / ".codegraph" / "codegraph.db").exists()


def _top_level_segment(path: str) -> str | None:
    """Retorna el primer segmento de un path normalizado (el directorio top-level).

    Retorna None si el archivo está en la raíz (sin directorio) o si el path
    está vacío.

    Ejemplos:
        'forge/cli.py'                 → 'forge'
        'forge/filters/analyzer.py'   → 'forge'
        'nuevo_modulo/x.py'           → 'nuevo_modulo'
        'README.md'                   → None
    """
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    # Si hay al menos dos partes, la primera es el directorio top-level
    if len(parts) >= 2 and parts[0]:
        return parts[0]
    return None


def _run_codegraph_files(root: Path, timeout: int = 10) -> str:
    """Ejecuta `codegraph files --format grouped --json` vía subprocess.

    Retorna el stdout como string. Lanza las excepciones hacia arriba — el
    manejo de fallback es responsabilidad del llamador.

    El flag `--format grouped` produce el mismo output flat que `--format flat`
    (shape verificado: array plano con {path, language, nodeCount, size}).
    """
    result = subprocess.run(
        ["codegraph", "files", "--format", "grouped", "--json"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result


def _filter_confirmed_modules(candidates: set, codegraph_entries: list) -> list:
    """Intersecta candidatos top-level con los módulos confirmados por codegraph.

    Un candidato se considera confirmado si:
        - codegraph tiene al menos un archivo con ese top-level como primer segmento
        - y ese archivo tiene nodeCount > 0 (módulo real con símbolos indexados)

    Args:
        candidates: set de strings con los top-levels derivados de changed_files.
        codegraph_entries: lista de dicts con shape {path, language, nodeCount, size}.

    Returns:
        Lista ordenada de top-levels confirmados.
    """
    confirmed: set[str] = set()
    for entry in codegraph_entries:
        try:
            path = entry["path"]
            node_count = entry["nodeCount"]
        except (KeyError, TypeError):
            # Estructura inesperada — ignorar esta entrada (parseo defensivo)
            continue
        segment = _top_level_segment(str(path))
        if segment and node_count > 0 and segment in candidates:
            confirmed.add(segment)
    return sorted(confirmed)


def detect_top_level_module_changes(root: Path, changed_files: list) -> list:
    """Detecta módulos top-level que aparecen como nuevos en changed_files y
    están confirmados por CodeGraph como módulos reales con símbolos.

    Estrategia híbrida (ADR-2):
        1. git/paths aportan candidatos: primer segmento de cada path en changed_files.
        2. CodeGraph confirma la realidad estructural: consulta `codegraph files` y
           filtra candidatos que tienen nodeCount > 0 en el índice actual.

    Fallback graceful (sin excepciones propagadas al llamador):
        - changed_files vacío → [] sin invocar subprocess.
        - codegraph no disponible (binario ausente o índice ausente) → [].
        - subprocess error (exit != 0, timeout, FileNotFoundError) → [].
        - JSON inválido o estructura inesperada → [].

    Args:
        root: raíz del proyecto (debe contener .codegraph/codegraph.db si disponible).
        changed_files: lista de paths modificados relativos al root.

    Returns:
        Lista de nombres de módulos top-level confirmados como nuevos.
    """
    # Optimización y prevención de ruido: sin changed_files no hay candidatos
    if not changed_files:
        return []

    if not codegraph_available(root):
        return []

    # Derivar candidatos top-level desde changed_files
    candidates = {
        seg
        for path in changed_files
        if (seg := _top_level_segment(str(path))) is not None
    }
    if not candidates:
        return []

    try:
        proc = _run_codegraph_files(root)
        if proc.returncode != 0:
            return []
        entries = json.loads(proc.stdout)
        if not isinstance(entries, list):
            return []
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, OSError):
        return []

    return _filter_confirmed_modules(candidates, entries)


def detect(changed_files: list, rev_a: str = None, rev_b: str = None) -> dict:
    """Análisis principal. Retorna un dict serializable a JSON.

    Args:
        changed_files: paths modificados, relativos al root del proyecto.
        rev_a: aceptado por compatibilidad de API con callers externos (no usado
               internamente — ADR-3). CodeGraph no compara revisiones.
        rev_b: ídem rev_a.
    """
    root = project_root()
    config = load_config(root)

    details = {
        "manifest_changes": [],
        "transversal_changes": [],
        "migration_changes": [],
        "new_top_level_modules": [],
    }

    for path in changed_files:
        if is_manifest(path, config["manifest_files"]):
            details["manifest_changes"].append(path)
        if is_under_path(path, config["transversal_paths"]):
            details["transversal_changes"].append(path)
        if is_under_path(path, config["migration_paths"]):
            details["migration_changes"].append(path)

    # La condición cambió de `rev_a and rev_b` a `changed_files` (ADR-1, ADR-3).
    # La señal temporal real proviene de changed_files (git); rev_a/rev_b no se usan
    # porque CodeGraph opera siempre sobre el índice actual.
    if changed_files:
        details["new_top_level_modules"] = detect_top_level_module_changes(root, changed_files)

    signals = []
    if details["manifest_changes"]:
        signals.append("new_dependencies")
    if details["transversal_changes"]:
        signals.append("transversal_module_change")
    if details["migration_changes"]:
        signals.append("db_migration")
    if details["new_top_level_modules"]:
        signals.append("new_top_level_module")

    return {
        "is_structural": bool(signals),
        "signals": signals,
        "details": details,
    }


def main() -> None:
    """CLI: lee lista de archivos modificados de stdin (un path por línea)."""
    changed_files = [line.strip() for line in sys.stdin if line.strip()]
    result = detect(changed_files)
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
