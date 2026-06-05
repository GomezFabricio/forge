"""Tests de forge.structural_detector.

Cubre detect_top_level_module_changes y su integración con detect().

Requisitos cubiertos:
- R-CG-01: detección real de módulos top-level nuevos
- R-CG-02: fallback graceful cuando codegraph no está disponible
- R-CG-03: parseo defensivo de la salida de la CLI

Constraints:
- CC-TMP-PATH: todo acceso a filesystem usa tmp_path.
- CC-NO-REAL-PROC: nunca invoca subprocess real ni requiere binario codegraph.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forge.structural_detector import (
    _top_level_segment,
    detect,
    detect_top_level_module_changes,
)

# ---------------------------------------------------------------------------
# Fixture: shape real de `codegraph files --format grouped --json`
# Verificado contra el índice real de forge (2026-06-04).
# Es un ARRAY PLANO — cada elemento tiene: path, language, nodeCount, size.
# ---------------------------------------------------------------------------

FIXTURE_CODEGRAPH_FILES = json.dumps([
    {"path": "config/modulos-transversales.yaml", "language": "yaml", "nodeCount": 0, "size": 3663},
    {"path": "forge/__init__.py", "language": "python", "nodeCount": 2, "size": 114},
    {"path": "forge/bootstrap.py", "language": "python", "nodeCount": 41, "size": 30835},
    {"path": "forge/cli.py", "language": "python", "nodeCount": 7, "size": 2436},
    {"path": "forge/filters/__init__.py", "language": "python", "nodeCount": 5, "size": 665},
    {"path": "nuevo_modulo/core.py", "language": "python", "nodeCount": 3, "size": 500},
])

FIXTURE_WITHOUT_NEW_MODULE = json.dumps([
    {"path": "forge/__init__.py", "language": "python", "nodeCount": 2, "size": 114},
    {"path": "forge/bootstrap.py", "language": "python", "nodeCount": 41, "size": 30835},
    {"path": "forge/cli.py", "language": "python", "nodeCount": 7, "size": 2436},
])

FIXTURE_MULTIPLE_MODULES = json.dumps([
    {"path": "forge/__init__.py", "language": "python", "nodeCount": 2, "size": 114},
    {"path": "nuevo_modulo/core.py", "language": "python", "nodeCount": 3, "size": 500},
    {"path": "otro_modulo/service.py", "language": "python", "nodeCount": 5, "size": 800},
    {"path": "no_confirmado/utils.py", "language": "python", "nodeCount": 0, "size": 200},
])


# ---------------------------------------------------------------------------
# Helper para construir un root con codegraph disponible
# ---------------------------------------------------------------------------

def _make_root_with_index(tmp_path: Path) -> Path:
    """Crea estructura mínima para que codegraph_available() retorne True."""
    (tmp_path / ".codegraph").mkdir()
    (tmp_path / ".codegraph" / "codegraph.db").touch()
    return tmp_path


# ---------------------------------------------------------------------------
# R-CG-02-a: binario codegraph ausente del PATH
# ---------------------------------------------------------------------------


class TestFallbackBinarioAusente:
    """R-CG-02: shutil.which('codegraph') retorna None → función retorna []."""

    def test_binario_ausente_retorna_lista_vacia(self, tmp_path):
        """GIVEN binario ausente WHEN detect_top_level_module_changes THEN []."""
        _make_root_with_index(tmp_path)
        with patch("forge.structural_detector.shutil.which", return_value=None):
            result = detect_top_level_module_changes(tmp_path, ["nuevo_modulo/x.py"])
        assert result == []

    def test_binario_ausente_no_lanza_excepcion(self, tmp_path):
        """GIVEN binario ausente THEN no se propaga ninguna excepción."""
        _make_root_with_index(tmp_path)
        with patch("forge.structural_detector.shutil.which", return_value=None):
            try:
                detect_top_level_module_changes(tmp_path, ["nuevo_modulo/x.py"])
            except Exception as exc:
                pytest.fail(f"Se propagó excepción inesperada: {exc}")


# ---------------------------------------------------------------------------
# R-CG-02-b: índice .codegraph/codegraph.db ausente
# ---------------------------------------------------------------------------


class TestFallbackIndiceAusente:
    """R-CG-02: binario presente pero índice ausente → función retorna []."""

    def test_indice_ausente_retorna_lista_vacia(self, tmp_path):
        """GIVEN binario presente e índice ausente THEN []."""
        # tmp_path no tiene .codegraph/codegraph.db
        with patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"):
            result = detect_top_level_module_changes(tmp_path, ["nuevo_modulo/x.py"])
        assert result == []


# ---------------------------------------------------------------------------
# R-CG-02-c: subprocess retorna exit code != 0
# ---------------------------------------------------------------------------


class TestFallbackExitCodeNoZero:
    """R-CG-02: subprocess exit code != 0 → función retorna []."""

    def test_exit_code_nonzero_retorna_lista_vacia(self, tmp_path):
        """GIVEN exit code != 0 THEN []."""
        _make_root_with_index(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch("forge.structural_detector.subprocess.run", return_value=mock_result),
        ):
            result = detect_top_level_module_changes(tmp_path, ["nuevo_modulo/x.py"])
        assert result == []


# ---------------------------------------------------------------------------
# R-CG-02-d: subprocess lanza TimeoutExpired
# ---------------------------------------------------------------------------


class TestFallbackTimeout:
    """R-CG-02: subprocess lanza TimeoutExpired → [] sin propagar."""

    def test_timeout_retorna_lista_vacia(self, tmp_path):
        """GIVEN TimeoutExpired THEN []."""
        _make_root_with_index(tmp_path)
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch(
                "forge.structural_detector.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="codegraph", timeout=10),
            ),
        ):
            result = detect_top_level_module_changes(tmp_path, ["nuevo_modulo/x.py"])
        assert result == []

    def test_timeout_no_propaga_excepcion(self, tmp_path):
        """GIVEN TimeoutExpired THEN no se propaga hacia el llamador."""
        _make_root_with_index(tmp_path)
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch(
                "forge.structural_detector.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="codegraph", timeout=10),
            ),
        ):
            try:
                detect_top_level_module_changes(tmp_path, ["nuevo_modulo/x.py"])
            except Exception as exc:
                pytest.fail(f"Se propagó TimeoutExpired: {exc}")


# ---------------------------------------------------------------------------
# R-CG-03-a: stdout no parseable como JSON
# ---------------------------------------------------------------------------


class TestParseoDefensivoNoJson:
    """R-CG-03: stdout no-JSON con exit 0 → [] sin JSONDecodeError."""

    def test_stdout_basura_retorna_lista_vacia(self, tmp_path):
        """GIVEN stdout con texto basura THEN []."""
        _make_root_with_index(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "esto no es json\nerror de syntaxis\n"
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch("forge.structural_detector.subprocess.run", return_value=mock_result),
        ):
            result = detect_top_level_module_changes(tmp_path, ["nuevo_modulo/x.py"])
        assert result == []

    def test_stdout_basura_no_lanza_json_decode_error(self, tmp_path):
        """GIVEN stdout basura THEN no se propaga JSONDecodeError."""
        _make_root_with_index(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json at all"
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch("forge.structural_detector.subprocess.run", return_value=mock_result),
        ):
            try:
                detect_top_level_module_changes(tmp_path, ["nuevo_modulo/x.py"])
            except json.JSONDecodeError as exc:
                pytest.fail(f"Se propagó JSONDecodeError: {exc}")


# ---------------------------------------------------------------------------
# R-CG-03-b: JSON válido pero estructura inesperada
# ---------------------------------------------------------------------------


class TestParseoDefensivoEstructuraInesperada:
    """R-CG-03: JSON válido pero estructura distinta a la esperada → []."""

    def test_json_objeto_en_lugar_de_array_retorna_vacio(self, tmp_path):
        """GIVEN JSON es un objeto (no array) THEN []."""
        _make_root_with_index(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"error": "unexpected"})
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch("forge.structural_detector.subprocess.run", return_value=mock_result),
        ):
            result = detect_top_level_module_changes(tmp_path, ["nuevo_modulo/x.py"])
        assert result == []

    def test_json_array_sin_campo_path_retorna_vacio(self, tmp_path):
        """GIVEN array con items sin campo 'path' THEN []."""
        _make_root_with_index(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([{"file": "algo.py", "nodeCount": 5}])
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch("forge.structural_detector.subprocess.run", return_value=mock_result),
        ):
            result = detect_top_level_module_changes(tmp_path, ["algo/x.py"])
        assert result == []


# ---------------------------------------------------------------------------
# R-CG-01-a: módulo top-level nuevo detectado correctamente
# ---------------------------------------------------------------------------


class TestDeteccionModuloTopLevelNuevo:
    """R-CG-01: changed_files contiene archivo de nuevo módulo confirmado por codegraph."""

    def test_modulo_nuevo_confirmado_retorna_nombre(self, tmp_path):
        """GIVEN changed_files=['nuevo_modulo/x.py'] y codegraph confirma nuevo_modulo THEN ['nuevo_modulo']."""
        _make_root_with_index(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = FIXTURE_CODEGRAPH_FILES
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch("forge.structural_detector.subprocess.run", return_value=mock_result),
        ):
            result = detect_top_level_module_changes(tmp_path, ["nuevo_modulo/x.py"])
        assert result == ["nuevo_modulo"]

    def test_modulo_nuevo_confirmado_no_lanza_excepcion(self, tmp_path):
        """GIVEN caso happy path THEN no se propaga excepción."""
        _make_root_with_index(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = FIXTURE_CODEGRAPH_FILES
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch("forge.structural_detector.subprocess.run", return_value=mock_result),
        ):
            try:
                detect_top_level_module_changes(tmp_path, ["nuevo_modulo/x.py"])
            except Exception as exc:
                pytest.fail(f"Se propagó excepción inesperada: {exc}")


# ---------------------------------------------------------------------------
# R-CG-01-b: sin módulos nuevos (changed_files no incluye ningún top-level
#            confirmado por codegraph porque el top-level en changed_files
#            no tiene entradas con nodeCount > 0)
# ---------------------------------------------------------------------------


class TestSinModulosNuevos:
    """R-CG-01: changed_files toca un top-level que NO aparece en el índice de codegraph → []."""

    def test_top_level_no_indexado_retorna_vacio(self, tmp_path):
        """GIVEN changed_files=['desconocido/x.py'] y codegraph no tiene ese top-level THEN []."""
        _make_root_with_index(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        # El índice solo conoce forge/ — no contiene desconocido/
        mock_result.stdout = FIXTURE_WITHOUT_NEW_MODULE
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch("forge.structural_detector.subprocess.run", return_value=mock_result),
        ):
            result = detect_top_level_module_changes(tmp_path, ["desconocido/x.py"])
        assert result == []


# ---------------------------------------------------------------------------
# Optimización: changed_files vacío → no invocar subprocess
# ---------------------------------------------------------------------------


class TestChangedFilesVacio:
    """Optimización: changed_files=[] → [] sin invocar subprocess."""

    def test_changed_files_vacio_retorna_lista_vacia(self, tmp_path):
        """GIVEN changed_files=[] THEN []."""
        _make_root_with_index(tmp_path)
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch("forge.structural_detector.subprocess.run"),
        ):
            result = detect_top_level_module_changes(tmp_path, [])
        assert result == []

    def test_changed_files_vacio_no_invoca_subprocess(self, tmp_path):
        """GIVEN changed_files=[] THEN subprocess.run NO es invocado."""
        _make_root_with_index(tmp_path)
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch("forge.structural_detector.subprocess.run") as mock_run,
        ):
            detect_top_level_module_changes(tmp_path, [])
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# Test de no-regresión de detect()
# ---------------------------------------------------------------------------


class TestNoRegresionDetect:
    """detect() con changed_files que no disparan codegraph mantiene su contrato de retorno."""

    def test_detect_retorna_shape_intacto(self, tmp_path):
        """GIVEN changed_files vacío THEN detect() retorna dict con claves esperadas."""
        result = detect([])
        assert "is_structural" in result
        assert "signals" in result
        assert "details" in result
        assert "new_top_level_modules" in result["details"]

    def test_detect_con_changed_files_incluye_new_top_level_modules(self, tmp_path):
        """GIVEN changed_files con archivos THEN new_top_level_modules presente en details."""
        # Simula que codegraph no está disponible — solo verifica el shape del resultado
        with patch("forge.structural_detector.shutil.which", return_value=None):
            result = detect(["forge/cli.py"])
        assert "new_top_level_modules" in result["details"]
        assert isinstance(result["details"]["new_top_level_modules"], list)


# ---------------------------------------------------------------------------
# Fase 4: TRIANGULATE — múltiples top-levels, solo algunos confirmados
# ---------------------------------------------------------------------------


class TestTriangulacionInterseccion:
    """TRIANGULATE: changed_files toca múltiples top-levels, codegraph confirma solo algunos."""

    def test_solo_confirma_modulos_con_node_count_mayor_a_cero(self, tmp_path):
        """GIVEN múltiples top-levels, algunos con nodeCount=0 THEN solo los confirmados."""
        _make_root_with_index(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = FIXTURE_MULTIPLE_MODULES
        # changed_files toca: nuevo_modulo, otro_modulo, no_confirmado
        # no_confirmado tiene nodeCount=0 → no debería aparecer
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch("forge.structural_detector.subprocess.run", return_value=mock_result),
        ):
            result = detect_top_level_module_changes(
                tmp_path,
                [
                    "nuevo_modulo/core.py",
                    "otro_modulo/service.py",
                    "no_confirmado/utils.py",
                ],
            )
        # forge no aparece en changed_files; no_confirmado tiene nodeCount=0
        assert "nuevo_modulo" in result
        assert "otro_modulo" in result
        assert "no_confirmado" not in result

    def test_archivos_en_raiz_no_generan_top_level(self, tmp_path):
        """GIVEN archivo en raíz (sin segmento de directorio) THEN no se genera candidato."""
        _make_root_with_index(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = FIXTURE_CODEGRAPH_FILES
        with (
            patch("forge.structural_detector.shutil.which", return_value="/usr/bin/codegraph"),
            patch("forge.structural_detector.subprocess.run", return_value=mock_result),
        ):
            result = detect_top_level_module_changes(tmp_path, ["README.md", "setup.py"])
        assert result == []


# ---------------------------------------------------------------------------
# Tests de _top_level_segment (helper puro)
# ---------------------------------------------------------------------------


class TestTopLevelSegment:
    """Tests del helper _top_level_segment(path) -> str | None."""

    def test_path_con_directorio_retorna_primer_segmento(self):
        """GIVEN 'forge/cli.py' THEN 'forge'."""
        assert _top_level_segment("forge/cli.py") == "forge"

    def test_path_con_subdirectorio_retorna_primer_segmento(self):
        """GIVEN 'forge/filters/analyzer.py' THEN 'forge'."""
        assert _top_level_segment("forge/filters/analyzer.py") == "forge"

    def test_archivo_en_raiz_retorna_none(self):
        """GIVEN 'README.md' (sin directorio) THEN None."""
        assert _top_level_segment("README.md") is None

    def test_path_con_backslash_normalizado(self):
        """GIVEN path con backslash Windows THEN normalizado correctamente."""
        assert _top_level_segment("forge\\cli.py") == "forge"
