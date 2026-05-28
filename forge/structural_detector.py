#!/usr/bin/env python3
"""Detector de cambios estructurales para forge.

Usado por /fg-review para decidir si marcar un cambio como `structural: true` y
sugerir /fg-update-arch al cerrar.

Inputs:
    - changed_files: lista de paths modificados en el cambio (relativos al root).
    - (opcional) git_rev_a, git_rev_b: revisiones para diff de topología via CodeGraph.

Output: dict con `is_structural`, `signals`, `details`.

Heurísticas (cualquiera de estas marca el cambio como estructural):
    1. Toca archivos de manifiesto (requirements.txt, package.json, go.mod, etc.).
    2. Toca paths declarados como transversales en config/modulos-transversales.yaml.
    3. Toca archivos de migración de BD.
    4. CodeGraph detecta módulos top-level nuevos entre rev_a y rev_b (si está disponible).

Si CodeGraph no está instalado, el detector se apoya solo en heurísticas de paths.
"""

import json
import shutil
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


def detect_top_level_module_changes(root: Path, rev_a: str, rev_b: str) -> list:
    """Placeholder de integración con CodeGraph.

    Cuando esté disponible la CLI específica de CodeGraph para diff de topología,
    este método debe ejecutar la query equivalente a:
        codegraph diff --top-level-modules <rev_a> <rev_b>

    Por ahora retorna [] (gracefully degraded) cuando codegraph no está disponible
    o cuando la CLI específica todavía no fue integrada.
    """
    if not codegraph_available(root):
        return []
    # TODO: integrar con la CLI real de CodeGraph cuando esté definida.
    return []


def detect(changed_files: list, rev_a: str = None, rev_b: str = None) -> dict:
    """Análisis principal. Retorna un dict serializable a JSON.

    Args:
        changed_files: paths modificados, relativos al root del proyecto.
        rev_a, rev_b: revisiones para diff de topología (opcional).
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

    if rev_a and rev_b:
        details["new_top_level_modules"] = detect_top_level_module_changes(root, rev_a, rev_b)

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
