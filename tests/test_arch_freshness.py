"""Tests para forge.arch_freshness — detector de arquitectura al día.

Cubre los escenarios de R-PORTERO-03.

Mecanismo: escanea docs/auditoria/cambios/*/README.md buscando
frontmatter con structural=true sin arch_synced=true.
Si no existe docs/arquitectura/overview.md → al_dia=False, sin_overview=True.
"""

import pytest

from forge.arch_freshness import check_arch_freshness


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------


def _crear_readme(tmp_path, cambio: str, frontmatter: str) -> None:
    """Crea un README con frontmatter YAML en la carpeta de cambio."""
    carpeta = tmp_path / "docs" / "auditoria" / "cambios" / cambio
    carpeta.mkdir(parents=True, exist_ok=True)
    contenido = f"---\n{frontmatter}\n---\n\n# Cambio {cambio}\n"
    (carpeta / "README.md").write_text(contenido, encoding="utf-8")


def _crear_overview(tmp_path) -> None:
    """Crea el archivo docs/arquitectura/overview.md."""
    overview_dir = tmp_path / "docs" / "arquitectura"
    overview_dir.mkdir(parents=True, exist_ok=True)
    (overview_dir / "overview.md").write_text("# Overview\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# R-PORTERO-03 — escenarios principales
# ---------------------------------------------------------------------------


class TestCheckArchFreshness:
    """Verifica los 4 escenarios del spec R-PORTERO-03."""

    def test_sin_cambios_estructurales_retorna_al_dia(self, tmp_path):
        """GIVEN carpeta sin cambios estructurales → al_dia=True, pendientes=0."""
        _crear_overview(tmp_path)
        cambios_dir = tmp_path / "docs" / "auditoria" / "cambios"
        cambios_dir.mkdir(parents=True, exist_ok=True)
        # Crear un cambio sin structural
        _crear_readme(tmp_path, "cambio-trivial", "structural: false")

        resultado = check_arch_freshness(
            cambios_dir=cambios_dir,
            arch_overview=tmp_path / "docs" / "arquitectura" / "overview.md",
        )

        assert resultado["al_dia"] is True
        assert resultado["pendientes"] == 0
        assert resultado["sin_overview"] is False

    def test_structural_sin_arch_synced_retorna_desactualizado(self, tmp_path):
        """GIVEN README con structural=true sin arch_synced → al_dia=False, pendientes=1."""
        _crear_overview(tmp_path)
        _crear_readme(tmp_path, "cambio-estructura", "structural: true")
        cambios_dir = tmp_path / "docs" / "auditoria" / "cambios"

        resultado = check_arch_freshness(
            cambios_dir=cambios_dir,
            arch_overview=tmp_path / "docs" / "arquitectura" / "overview.md",
        )

        assert resultado["al_dia"] is False
        assert resultado["pendientes"] == 1

    def test_structural_con_arch_synced_true_retorna_al_dia(self, tmp_path):
        """GIVEN structural=true + arch_synced=true → ese cambio NO cuenta como pendiente."""
        _crear_overview(tmp_path)
        _crear_readme(
            tmp_path,
            "cambio-sincronizado",
            "structural: true\narch_synced: true",
        )
        cambios_dir = tmp_path / "docs" / "auditoria" / "cambios"

        resultado = check_arch_freshness(
            cambios_dir=cambios_dir,
            arch_overview=tmp_path / "docs" / "arquitectura" / "overview.md",
        )

        assert resultado["al_dia"] is True
        assert resultado["pendientes"] == 0

    def test_sin_overview_retorna_desactualizado_y_sin_overview(self, tmp_path):
        """GIVEN sin docs/arquitectura/overview.md → al_dia=False, sin_overview=True."""
        cambios_dir = tmp_path / "docs" / "auditoria" / "cambios"
        cambios_dir.mkdir(parents=True, exist_ok=True)
        overview_path = tmp_path / "docs" / "arquitectura" / "overview.md"
        # NO crear el overview

        resultado = check_arch_freshness(
            cambios_dir=cambios_dir,
            arch_overview=overview_path,
        )

        assert resultado["al_dia"] is False
        assert resultado["sin_overview"] is True


# ---------------------------------------------------------------------------
# Triangulación — escenarios adicionales para forzar lógica real
# ---------------------------------------------------------------------------


class TestCheckArchFreshnessTriangulacion:
    """Casos de borde que fuerzan la lógica más allá del happy path."""

    def test_multiples_cambios_uno_pendiente_cuenta_uno(self, tmp_path):
        """GIVEN 3 cambios (1 structural sin sync, 2 sincronizados) → pendientes=1."""
        _crear_overview(tmp_path)
        _crear_readme(tmp_path, "c1", "structural: true\narch_synced: true")
        _crear_readme(tmp_path, "c2", "structural: true")  # pendiente
        _crear_readme(tmp_path, "c3", "structural: false")
        cambios_dir = tmp_path / "docs" / "auditoria" / "cambios"

        resultado = check_arch_freshness(
            cambios_dir=cambios_dir,
            arch_overview=tmp_path / "docs" / "arquitectura" / "overview.md",
        )

        assert resultado["al_dia"] is False
        assert resultado["pendientes"] == 1

    def test_multiples_cambios_todos_sincronizados_retorna_al_dia(self, tmp_path):
        """GIVEN 3 cambios todos con arch_synced=true → al_dia=True."""
        _crear_overview(tmp_path)
        for i in range(3):
            _crear_readme(tmp_path, f"c{i}", "structural: true\narch_synced: true")
        cambios_dir = tmp_path / "docs" / "auditoria" / "cambios"

        resultado = check_arch_freshness(
            cambios_dir=cambios_dir,
            arch_overview=tmp_path / "docs" / "arquitectura" / "overview.md",
        )

        assert resultado["al_dia"] is True
        assert resultado["pendientes"] == 0

    def test_carpeta_cambios_inexistente_retorna_al_dia(self, tmp_path):
        """GIVEN carpeta de cambios no existe → sin pendientes → al_dia=True (si hay overview)."""
        _crear_overview(tmp_path)
        cambios_dir = tmp_path / "docs" / "auditoria" / "cambios"
        # NO crear la carpeta

        resultado = check_arch_freshness(
            cambios_dir=cambios_dir,
            arch_overview=tmp_path / "docs" / "arquitectura" / "overview.md",
        )

        assert resultado["al_dia"] is True
        assert resultado["pendientes"] == 0

    def test_readme_sin_frontmatter_ignorado(self, tmp_path):
        """GIVEN README sin frontmatter YAML → no se cuenta como pendiente."""
        _crear_overview(tmp_path)
        carpeta = tmp_path / "docs" / "auditoria" / "cambios" / "sin-fm"
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "README.md").write_text("# Sin frontmatter\n", encoding="utf-8")
        cambios_dir = tmp_path / "docs" / "auditoria" / "cambios"

        resultado = check_arch_freshness(
            cambios_dir=cambios_dir,
            arch_overview=tmp_path / "docs" / "arquitectura" / "overview.md",
        )

        assert resultado["al_dia"] is True
        assert resultado["pendientes"] == 0

    def test_arch_synced_false_explícito_cuenta_como_pendiente(self, tmp_path):
        """GIVEN structural=true + arch_synced=false → cuenta como pendiente."""
        _crear_overview(tmp_path)
        _crear_readme(
            tmp_path, "no-sync", "structural: true\narch_synced: false"
        )
        cambios_dir = tmp_path / "docs" / "auditoria" / "cambios"

        resultado = check_arch_freshness(
            cambios_dir=cambios_dir,
            arch_overview=tmp_path / "docs" / "arquitectura" / "overview.md",
        )

        assert resultado["al_dia"] is False
        assert resultado["pendientes"] == 1
