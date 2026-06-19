"""forge install — global asset installer.

Orchestrates:
  1. detect_engram()            — check if engram is already available
  2. install_engram()           — download binary, edit PATH, register MCP (optional)
  3. detect_codegraph()         — check if codegraph is already available
  4. install_codegraph()        — download binary, verify SHA256, extract, edit PATH
  5. register_codegraph_mcp()   — merge mcpServers.codegraph into ~/.claude.json
  6. install_assets()           — deposit skills, agents into ~/.claude/
  7. print_report()             — human-readable summary

CodeGraph helpers (PR-A — puros, sin red ni subprocess):
  detect_codegraph()       — detecta binario codegraph en PATH (shutil.which)
  _codegraph_asset_name()  — mapea (os, arch) → nombre del asset de release
  _verify_sha256()         — verifica integridad SHA256 del binario descargado

Exit codes:
  EXIT_OK                  = 0   — success
  EXIT_ABORTED             = 10  — user declined engram install prompt
  EXIT_ENGRAM_INSTALL_FAILED = 20 — download or PATH edit failed
  EXIT_DEPOSIT_FAILED      = 30  — share/forge/ not found or write error
  EXIT_PLATFORM_UNSUPPORTED = 40 — OS / arch not in supported map

Usage:
    Called via cli.cmd_install(args) -> installer.run(args).
    Not meant to be run directly.
"""

import contextlib
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# TODO(ruamel-yaml): switch to ruamel.yaml if _shared/*.md gain YAML comments
import yaml

# =============================================================================
# === Constants ===
# =============================================================================

EXIT_OK = 0
EXIT_ABORTED = 10          # user said N to engram install prompt
EXIT_ENGRAM_INSTALL_FAILED = 20  # download or PATH edit failed
EXIT_DEPOSIT_FAILED = 30   # share/forge/ not found or write error
EXIT_PLATFORM_UNSUPPORTED = 40  # OS / arch not in supported map

CLAUDE_HOME = Path.home() / ".claude"
ENGRAM_BIN_DIR_UNIX = Path.home() / ".engram" / "bin"
ENGRAM_BIN_DIR_WIN = Path.home() / ".engram" / "bin"
# Unified alias — both platform variants are identical; prefer this in new code.
ENGRAM_BIN_DIR = ENGRAM_BIN_DIR_UNIX

GITHUB_RELEASES_API = (
    "https://api.github.com/repos/Gentleman-Programming/engram/releases/latest"
)

# Q1 (resolved in apply): assets are tarballs: engram_{ver}_{os}_{arch}.tar.gz
# Windows uses .zip. Binary is extracted from archive post-download.
# Naming: engram_{version}_{os}_{arch}[.tar.gz|.zip]
# OS tokens: linux, darwin, windows
# Arch tokens: amd64, arm64

# =============================================================================
# === Constantes CodeGraph ===
# =============================================================================

CODEGRAPH_REPO = "colbymchenry/codegraph"
CODEGRAPH_GITHUB_RELEASES_API = (
    f"https://api.github.com/repos/{CODEGRAPH_REPO}/releases/latest"
)
CODEGRAPH_BIN_DIR_UNIX = Path.home() / ".codegraph" / "bin"
CODEGRAPH_BIN_DIR_WIN = Path.home() / ".codegraph" / "bin"

# Path monkeypatcheable para tests — NO usar Path.home() directamente en lógica testeable.
# CLAUDE_JSON is the canonical name; CODEGRAPH_CLAUDE_JSON is kept as an alias for backward compat.
CLAUDE_JSON: Path = Path.home() / ".claude.json"
CODEGRAPH_CLAUDE_JSON: Path = CLAUDE_JSON

# Mapa de tokens (os, arch) → nombre de asset en el release de CodeGraph.
# IMPORTANTE: tokens DISTINTOS a engram.
#   OS tokens:   darwin | linux | win32   (engram usa: darwin | linux | windows)
#   Arch tokens: arm64 | x64              (engram usa: arm64 | amd64)
#   Extensión:   .zip en win32, .tar.gz en darwin/linux
_CODEGRAPH_ASSET_MAP: dict[tuple[str, str], str] = {
    ("darwin", "arm64"): "codegraph-darwin-arm64.tar.gz",
    ("darwin", "x64"):   "codegraph-darwin-x64.tar.gz",
    ("linux",  "x64"):   "codegraph-linux-x64.tar.gz",
    ("linux",  "arm64"): "codegraph-linux-arm64.tar.gz",
    ("win32",  "x64"):   "codegraph-win32-x64.zip",
    ("win32",  "arm64"): "codegraph-win32-arm64.zip",
}

# Bloque MCP que se registra en ~/.claude.json bajo mcpServers.codegraph
_CODEGRAPH_MCP_BLOCK: dict = {
    "type": "stdio",
    "command": "codegraph",
    "args": ["serve", "--mcp"],
}

# Bloque MCP que se registra en ~/.claude.json bajo mcpServers.context7.
# Alternativa HTTP remota rechazada: requiere URL + header auth y depende de conectividad;
# stdio via npx es cero-infraestructura para un dev con Node instalado.
_CONTEXT7_MCP_BLOCK: dict = {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@upstash/context7-mcp"],
}

# Bloque MCP base para engram en ~/.claude.json bajo mcpServers.engram.
# El command se resuelve en register_engram_mcp(): ruta absoluta al binario cuando
# el instalador lo conoce (más robusto que depender del PATH para MCP spawning),
# o "engram" como fallback si solo se detectó vía which/--version.
_ENGRAM_MCP_ARGS: list = ["mcp", "--tools=agent"]

# Módulo del hook PII (UserPromptSubmit). Es la firma estable para idempotencia:
# el path del intérprete puede variar entre instalaciones, el módulo no.
PII_HOOK_MODULE = "forge.filters.hook_user_prompt"

# Módulo del hook de guardrails (PreToolUse). Firma estable para idempotencia.
GUARD_HOOK_MODULE = "forge.guards.hook_pre_tool"

# Mapa OS/arch para CodeGraph (tokens distintos a engram — win32/x64 en vez de windows/amd64)
_CODEGRAPH_OS_MAP: dict[str, str] = {
    "linux": "linux",
    "darwin": "darwin",
    "win32": "win32",
}
_CODEGRAPH_ARCH_MAP: dict[str, str] = {
    "x86_64": "x64",
    "amd64":  "x64",
    "arm64":  "arm64",
    "aarch64": "arm64",
}

PROMPT_CODEGRAPH_TEXT = """\
CodeGraph no detectado.

Forge puede instalar CodeGraph automáticamente para habilitar el análisis
estructural del codebase en tus sesiones de Claude Code.

Si confirmás, voy a:
  1. Descargar el binario oficial de CodeGraph desde GitHub Releases.
  2. Verificar su integridad SHA256.
  3. Instalarlo en ~/.codegraph/bin/.
  4. Registrar el MCP en ~/.claude.json para que Claude Code lo levante.

¿Lo instalo ahora? [Y/n]: """

PROMPT_CONTEXT7_TEXT = """\
Context7 MCP no registrado.

Forge puede registrar Context7 en tu ~/.claude.json para que Claude Code
acceda a documentación actualizada de librerías externas vía npx.

No se descarga ningún binario — Context7 corre on-demand mediante npx.
El cupo gratuito es de 1000 req/mes (pool anónimo compartido).
Para cupo personal, definí CONTEXT7_API_KEY en tu entorno.

¿Lo registro ahora? [Y/n]: """

PROMPT_TEXT = """\
Engram no detectado.

Forge usa engram para preservar las decisiones del workflow SDD entre
sesiones. Sin engram, cada nuevo prompt arranca sin contexto previo —
perdés continuidad entre el lunes y el martes, entre features, entre
ciclos.

Si confirmás, voy a:
  1. Descargar el binario oficial de engram desde GitHub Releases
     (~12 MB, no requiere Go ni otras herramientas).
  2. Instalarlo en %USERPROFILE%\\.engram\\bin\\engram.exe
     (en Linux/macOS: ~/.engram/bin/engram).
  3. Agregarlo al PATH del usuario.
  4. Registrar el MCP en ~/.claude.json (mcpServers.engram) para
     que Claude Code lo levante automáticamente.

Si preferís instalarlo por tu cuenta (brew, pacman, manual), respondé N
y volvé a correr 'forge install' cuando lo tengas listo.

¿Lo instalo ahora? [y/N]: """

# Keys required in forge-shared SKILL.md files (non-invocable companions)
_REQUIRED_FM_KEYS: dict = {"disable-model-invocation": True, "user-invocable": False}

# Cross-cutting _shared files that go to forge-shared/ (with frontmatter injection)
_CROSS_CUTTING = {"skill-resolver", "engram-protocol", "fg-phase-common"}

POST_INSTALL_MESSAGE = """\
forge instalado. A partir de ahora, charlá normal con Claude en cualquier
proyecto — el workflow se activa solo según el contexto.

Las skills (/fg-setup, /fg-explore, /fg-plan, /fg-design, /fg-implement,
/fg-review, /fg-update-arch, /fg-update-registry) existen como comandos por si
las querés invocar manualmente, pero no necesitás conocerlas."""

# =============================================================================
# === Detection ===
# =============================================================================


def detect_engram() -> tuple[bool, dict]:
    """Detect if engram is available via 3 ordered indicators.

    Returns:
        (True, info)  — first positive indicator; info has the triggering key set.
        (False, info) — all 3 indicators negative.

    Pure w.r.t. network and filesystem writes. Only reads + subprocess exec.
    """
    info: dict[str, str | None] = {
        "mcp_json": None,
        "which": None,
        "version_check": None,
    }

    # Indicator 1: mcpServers.engram entry in ~/.claude.json with a resolvable command
    claude_json_path = CODEGRAPH_CLAUDE_JSON  # ~/.claude.json — same file, no duplicate path
    if claude_json_path.exists():
        try:
            data = json.loads(claude_json_path.read_text(encoding="utf-8"))
            servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
            engram_block = servers.get("engram", {}) if isinstance(servers, dict) else {}
            cmd = engram_block.get("command") if isinstance(engram_block, dict) else None
            if cmd:
                # Accept the entry only when the binary is actually usable:
                #   - generic "engram": require shutil.which to confirm it is on PATH
                #   - absolute path:    require the file exists AND is executable
                if cmd == "engram":
                    usable = shutil.which("engram") is not None
                else:
                    p = Path(cmd)
                    usable = p.exists() and os.access(cmd, os.X_OK)
                if usable:
                    info["mcp_json"] = cmd
                    return True, info
        except (json.JSONDecodeError, OSError):
            pass  # corrupted file — fall through to indicator 2

    # Indicator 2: engram binary in PATH
    found = shutil.which("engram")
    if found:
        info["which"] = found
        return True, info

    # Indicator 3: engram --version responds with returncode 0
    try:
        result = subprocess.run(
            ["engram", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info["version_check"] = result.stdout.strip() or "ok"
            return True, info
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return False, info


# =============================================================================
# === CodeGraph helpers (PR-A — puros, sin red ni subprocess) ===
# =============================================================================


def detect_codegraph() -> tuple[bool, dict]:
    """Detecta si el binario codegraph está disponible en PATH.

    Usa únicamente shutil.which('codegraph') como indicador.
    Función pura: no escribe en el filesystem, no hace llamadas de red,
    no invoca subprocess.

    Returns:
        (True, {'which': ruta})  — codegraph encontrado en PATH
        (False, {})              — codegraph no encontrado o error de acceso
    """
    try:
        found = shutil.which("codegraph")
    except OSError:
        return False, {}

    if found:
        return True, {"which": found}
    return False, {}


def _codegraph_asset_name(os_tok: str, arch_tok: str) -> str:
    """Retorna el nombre del asset de release de CodeGraph para la plataforma dada.

    Tokens OS válidos:   darwin | linux | win32
    Tokens arch válidos: arm64 | x64

    IMPORTANTE: estos tokens son distintos a los de engram
    (engram usa 'windows'/'amd64'; codegraph usa 'win32'/'x64').

    Args:
        os_tok:   Token de sistema operativo (darwin, linux, win32).
        arch_tok: Token de arquitectura (arm64, x64).

    Returns:
        Nombre del archivo de asset (ej: 'codegraph-linux-x64.tar.gz').

    Raises:
        ValueError: si la combinación (os_tok, arch_tok) no está soportada.
    """
    key = (os_tok, arch_tok)
    asset = _CODEGRAPH_ASSET_MAP.get(key)
    if asset is None:
        supported = ", ".join(f"{o}/{a}" for o, a in _CODEGRAPH_ASSET_MAP)
        raise ValueError(
            f"Plataforma no soportada para CodeGraph: {os_tok}/{arch_tok}. "
            f"Combinaciones soportadas: {supported}"
        )
    return asset


def _verify_sha256(file_path: Path, sha256sums_content: str, asset_name: str) -> tuple[bool, str]:
    """Verifica la integridad SHA256 de un archivo descargado.

    Formato esperado de sha256sums_content: cada línea es
        <hash_hex><DOS_ESPACIOS><nombre_archivo>
    (formato estándar de sha256sum; dos espacios entre hash y nombre).

    Args:
        file_path:          Ruta al archivo descargado a verificar.
        sha256sums_content: Contenido completo del archivo SHA256SUMS del release.
        asset_name:         Nombre del asset a buscar en SHA256SUMS.

    Returns:
        (True, 'ok')                              — hash coincide
        (False, 'not found: <asset_name>')        — asset no encontrado en SHA256SUMS
        (False, 'hash mismatch: expected X got Y') — hash no coincide
    """
    # Buscar la línea del asset en SHA256SUMS
    expected_hash: str | None = None
    for line in sha256sums_content.splitlines():
        # Formato: "<hash>  <nombre>" (dos espacios)
        parts = line.split("  ", 1)
        if len(parts) == 2 and parts[1].strip() == asset_name:
            expected_hash = parts[0].strip()
            break

    if expected_hash is None:
        return False, f"not found: {asset_name}"

    # Calcular el hash real del archivo
    actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

    if actual_hash != expected_hash:
        return False, f"hash mismatch: expected {expected_hash} got {actual_hash}"

    return True, "ok"


# =============================================================================
# === CodeGraph install (PR-B) ===
# =============================================================================


def _detect_codegraph_platform() -> tuple[str, str]:
    """Detecta OS y arch con los tokens propios de CodeGraph (win32/x64, no windows/amd64).

    Returns:
        (os_token, arch_token) donde los tokens coinciden con el naming de releases de CodeGraph.

    Raises:
        SystemExit(EXIT_PLATFORM_UNSUPPORTED): si la plataforma no está soportada.
    """
    plat = sys.platform           # 'linux', 'darwin', 'win32'
    mach = platform.machine().lower()
    if plat not in _CODEGRAPH_OS_MAP or mach not in _CODEGRAPH_ARCH_MAP:
        raise SystemExit(EXIT_PLATFORM_UNSUPPORTED)
    return _CODEGRAPH_OS_MAP[plat], _CODEGRAPH_ARCH_MAP[mach]


def install_codegraph() -> tuple[bool, str]:
    """Descarga, verifica e instala el binario de CodeGraph.

    Nunca lanza excepciones — devuelve (False, mensaje de error) ante cualquier fallo.

    Flujo:
      1. _detect_codegraph_platform() → (os_tok, arch_tok)
      2. GET CODEGRAPH_GITHUB_RELEASES_API → tag_name + assets
      3. Encontrar asset y SHA256SUMS por nombre
      4. Descargar asset a tmpfile con _download_binary()
      5. GET SHA256SUMS → verificar con _verify_sha256()
      6. Extraer binario (tar.gz en unix, zip en win32) — flatten a bin_dir
      7. chmod +x en unix, _xattr_cleanup_darwin en darwin
      8. Editar PATH (_edit_path_unix/_edit_path_windows)

    Returns:
        (True, mensaje de éxito con ruta del binario)
        (False, mensaje de error descriptivo)
    """
    import tarfile
    import tempfile
    import zipfile

    try:
        os_tok, arch_tok = _detect_codegraph_platform()
    except SystemExit:
        return False, f"Plataforma no soportada para CodeGraph: {sys.platform}/{platform.machine()}"

    try:
        asset_name = _codegraph_asset_name(os_tok, arch_tok)
    except ValueError as exc:
        return False, str(exc)

    # Obtener metadata del release
    try:
        with urllib.request.urlopen(CODEGRAPH_GITHUB_RELEASES_API, timeout=15) as resp:
            release = json.loads(resp.read())
    except (urllib.error.URLError, OSError) as exc:
        return False, f"No se pudo obtener la release de CodeGraph: {exc}"

    assets = release.get("assets", [])

    # Buscar el asset del binario
    asset = next((a for a in assets if a["name"] == asset_name), None)
    if asset is None:
        available = [a["name"] for a in assets]
        return False, (
            f"Asset no encontrado para {os_tok}/{arch_tok}: {asset_name}. "
            f"Assets disponibles: {available}"
        )

    # Buscar SHA256SUMS
    sha256sums_asset = next((a for a in assets if a["name"] == "SHA256SUMS"), None)

    # Elegir directorio destino
    bin_dir = CODEGRAPH_BIN_DIR_WIN if os_tok == "win32" else CODEGRAPH_BIN_DIR_UNIX
    ext = ".zip" if os_tok == "win32" else ".tar.gz"
    bin_name = "codegraph.exe" if os_tok == "win32" else "codegraph"
    binary_dest = bin_dir / bin_name

    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path_str = tmp.name

        _download_binary(asset["browser_download_url"], Path(tmp_path_str))

        # Verificar SHA256 si está disponible
        if sha256sums_asset is not None:
            try:
                with urllib.request.urlopen(sha256sums_asset["browser_download_url"], timeout=15) as resp:
                    sha256sums_content = resp.read().decode("utf-8")
                ok, verify_msg = _verify_sha256(Path(tmp_path_str), sha256sums_content, asset_name)
                if not ok:
                    os.unlink(tmp_path_str)
                    return False, f"Verificación SHA256 fallida: {verify_msg}"
            except (urllib.error.URLError, OSError):
                # Si no se puede descargar SHA256SUMS, continuar sin verificar (advertencia)
                pass

        binary_dest.parent.mkdir(parents=True, exist_ok=True)

        if ext == ".tar.gz":
            with tarfile.open(tmp_path_str, "r:gz") as tf:
                # Encontrar el binario dentro del archivo (puede estar en subcarpeta)
                member = next(
                    (m for m in tf.getmembers()
                     if m.name.endswith("codegraph") or m.name.endswith("codegraph.exe")),
                    None,
                )
                if member is None:
                    os.unlink(tmp_path_str)
                    return False, "Binario 'codegraph' no encontrado dentro del tarball."
                member.name = bin_name  # flatten: eliminar subcarpetas del path
                # filter="data" hardens against symlink attacks (Python 3.12+).
                if sys.version_info >= (3, 12):
                    tf.extract(member, path=str(binary_dest.parent), filter="data")
                else:
                    tf.extract(member, path=str(binary_dest.parent))
        else:
            with zipfile.ZipFile(tmp_path_str, "r") as zf:
                member = next(
                    (n for n in zf.namelist()
                     if n.endswith("codegraph") or n.endswith("codegraph.exe")),
                    None,
                )
                if member is None:
                    os.unlink(tmp_path_str)
                    return False, "Binario 'codegraph' no encontrado dentro del zip."
                with zf.open(member) as src, open(binary_dest, "wb") as dst:
                    dst.write(src.read())

        os.unlink(tmp_path_str)

    except (urllib.error.URLError, OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        return False, f"Error descargando/extrayendo CodeGraph: {exc}"

    # chmod +x en unix
    if os_tok != "win32":
        os.chmod(binary_dest, 0o755)

    # macOS quarantine cleanup (best-effort)
    _xattr_cleanup_darwin(binary_dest)

    # Editar PATH
    if os_tok == "win32":
        _edit_path_windows(bin_dir)
    else:
        _edit_path_unix(bin_dir)

    return True, f"codegraph instalado en {binary_dest}"


def _backup_once(path: Path, backed_up: set) -> None:
    """Write a .forge-bak of *path* the FIRST time it is about to be mutated.

    Subsequent calls for the same path are no-ops — this preserves the pristine
    pre-install state across sequential registrar calls within a single run().

    Args:
        path:       The file that is about to be mutated.
        backed_up:  A run-scoped set of already-backed-up path strings.
                    Callers must pass the same set instance for the entire run.
    """
    key = str(path)
    if key in backed_up:
        return
    backed_up.add(key)
    if path.exists():
        bak = path.with_suffix(path.suffix + ".forge-bak")
        # Never overwrite an existing backup. A registrar may have created the
        # pristine .forge-bak already (e.g. install_engram() runs before the
        # codegraph registrar and is not tracked by this run's set); overwriting
        # here would clobber the pristine snapshot with mutated content.
        if not bak.exists():
            with contextlib.suppress(OSError):
                bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def register_codegraph_mcp() -> str:
    """Registra el bloque MCP de CodeGraph en ~/.claude.json con merge idempotente.

    Lee el JSON existente (o {} si ausente/corrupto), verifica si mcpServers.codegraph
    ya existe (idempotencia), crea backup .forge-bak antes de escribir y hace merge
    preservando el resto de la configuración.

    Returns:
        'present'  — el bloque ya existía y es válido, no se modificó nada
        'created'  — el archivo no existía o estaba vacío, se creó con el bloque
        'merged'   — el archivo existía con otra config, se hizo merge
    """
    claude_json_path = CODEGRAPH_CLAUDE_JSON

    # Leer configuración existente
    existing_content: str | None = None
    config: dict = {}
    if claude_json_path.exists():
        try:
            existing_content = claude_json_path.read_text(encoding="utf-8")
            config = json.loads(existing_content) or {}
            if not isinstance(config, dict):
                config = {}
        except (json.JSONDecodeError, OSError):
            config = {}

    # Idempotencia: si el bloque ya existe y es válido, no tocar nada
    mcp_servers = config.get("mcpServers", {})
    if isinstance(mcp_servers, dict) and "codegraph" in mcp_servers:
        return "present"

    # Crear backup antes de escribir — solo si aún no existe (preserva pristine de run())
    if existing_content is not None:
        backup_path = claude_json_path.with_suffix(".json.forge-bak")
        if not backup_path.exists():
            with contextlib.suppress(OSError):
                backup_path.write_text(existing_content, encoding="utf-8")

    # Merge: agregar mcpServers.codegraph preservando el resto
    if "mcpServers" not in config or not isinstance(config.get("mcpServers"), dict):
        config["mcpServers"] = {}
    config["mcpServers"]["codegraph"] = _CODEGRAPH_MCP_BLOCK

    # Determinar status antes de escribir
    was_empty = existing_content is None or existing_content.strip() == ""

    claude_json_path.parent.mkdir(parents=True, exist_ok=True)
    claude_json_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return "created" if was_empty else "merged"


def prompt_codegraph_yn() -> str:
    """Muestra el prompt de instalación de CodeGraph y lee la respuesta y/N.

    Default: instalar (Y). En entorno no-interactivo (stdin no es tty) retorna 'y'
    sin mostrar prompt ni llamar a input(), para no colgar en CI.

    Returns:
        'y' — instalar (incluyendo default por enter vacío y entornos no-interactivos)
        'n' — no instalar
    """
    # Entorno no-interactivo/CI: no colgar, instalar por defecto
    if not sys.stdin.isatty():
        return "y"

    response = input(PROMPT_CODEGRAPH_TEXT).strip().lower()
    # Default Y: vacío o afirmativo
    if response in {"", "y", "yes"}:
        return "y"
    return "n"


def register_context7_mcp() -> str:
    """Registra el bloque MCP de Context7 en ~/.claude.json con merge idempotente.

    Lee el JSON existente (o {} si ausente/corrupto), verifica si mcpServers.context7
    ya existe (idempotencia), crea backup .forge-bak antes de escribir y hace merge
    preservando el resto de la configuración.

    Si la variable de entorno CONTEXT7_API_KEY está definida y no vacía, inyecta
    --api-key <valor> en los args del bloque. La constante _CONTEXT7_MCP_BLOCK
    nunca se muta — se trabaja sobre una copia.

    Returns:
        'present'  — el bloque ya existía, no se modificó nada
        'created'  — el archivo no existía o estaba vacío, se creó con el bloque
        'merged'   — el archivo existía con otra config, se hizo merge
    """
    claude_json_path = CODEGRAPH_CLAUDE_JSON  # mismo archivo ~/.claude.json, no duplicar path

    # Leer configuración existente
    existing_content: str | None = None
    config: dict = {}
    if claude_json_path.exists():
        try:
            existing_content = claude_json_path.read_text(encoding="utf-8")
            config = json.loads(existing_content) or {}
            if not isinstance(config, dict):
                config = {}
        except (json.JSONDecodeError, OSError):
            config = {}

    # Idempotencia: si el bloque ya existe, no tocar nada
    mcp_servers = config.get("mcpServers", {})
    if isinstance(mcp_servers, dict) and "context7" in mcp_servers:
        return "present"

    # Crear backup antes de escribir — solo si aún no existe (preserva pristine de run())
    if existing_content is not None:
        backup_path = claude_json_path.with_suffix(".json.forge-bak")
        if not backup_path.exists():
            with contextlib.suppress(OSError):
                backup_path.write_text(existing_content, encoding="utf-8")

    # Construir el bloque a escribir (copiar base, no mutar la constante)
    api_key = os.environ.get("CONTEXT7_API_KEY", "")
    if api_key:
        block = dict(_CONTEXT7_MCP_BLOCK)
        block["args"] = list(_CONTEXT7_MCP_BLOCK["args"]) + ["--api-key", api_key]
    else:
        block = dict(_CONTEXT7_MCP_BLOCK)

    # Merge: agregar mcpServers.context7 preservando el resto
    if "mcpServers" not in config or not isinstance(config.get("mcpServers"), dict):
        config["mcpServers"] = {}
    config["mcpServers"]["context7"] = block

    # Determinar status antes de escribir
    was_empty = existing_content is None or existing_content.strip() == ""

    claude_json_path.parent.mkdir(parents=True, exist_ok=True)
    claude_json_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return "created" if was_empty else "merged"


def _hook_command(module: str) -> str:
    """Build a hook command that invokes *module* via the current interpreter.

    Uses sys.executable (the venv Python where forge is installed) rather than
    a generic 'python' that may not have forge importable. Quotes the path when
    it contains spaces (e.g. 'C:\\Program Files\\...').

    Args:
        module: fully-qualified Python module name (e.g. 'forge.filters.hook_user_prompt')

    Returns:
        A command string of the form ``<python> -m <module>``.
    """
    py = sys.executable or "python"
    if " " in py:
        py = f'"{py}"'
    return f"{py} -m {module}"


def _pii_hook_command() -> str:
    """Comando del hook PII, pinneado al intérprete actual."""
    return _hook_command(PII_HOOK_MODULE)


def _pii_hook_already_registered(user_prompt_submit: list) -> bool:
    """True si algún hook de UserPromptSubmit ya invoca el módulo PII de forge."""
    for group in user_prompt_submit:
        if not isinstance(group, dict):
            continue
        for hook in group.get("hooks", []) or []:
            if isinstance(hook, dict) and PII_HOOK_MODULE in str(hook.get("command", "")):
                return True
    return False


def register_pii_hook() -> str:
    """Registra el hook PII UserPromptSubmit en ~/.claude/settings.json (merge idempotente).

    Lee el settings.json existente (o {} si ausente/corrupto), verifica si el hook PII
    de forge ya está registrado (idempotencia por módulo), crea backup .forge-bak antes
    de escribir y hace merge preservando el resto de la config y los demás hooks.

    Returns:
        'present' — el hook ya estaba registrado, no se modificó nada
        'created' — settings.json no existía o estaba vacío, se creó con el hook
        'merged'  — settings.json existía con otra config, se hizo merge
    """
    settings_path = CLAUDE_HOME / "settings.json"

    existing_content: str | None = None
    config: dict = {}
    if settings_path.exists():
        try:
            existing_content = settings_path.read_text(encoding="utf-8")
            config = json.loads(existing_content) or {}
            if not isinstance(config, dict):
                config = {}
        except (json.JSONDecodeError, OSError):
            config = {}

    # Idempotencia: si el hook PII ya existe, no tocar nada
    hooks = config.get("hooks")
    if isinstance(hooks, dict):
        ups = hooks.get("UserPromptSubmit")
        if isinstance(ups, list) and _pii_hook_already_registered(ups):
            return "present"

    # Backup antes de escribir
    if existing_content is not None:
        backup_path = settings_path.with_suffix(".json.forge-bak")
        with contextlib.suppress(OSError):
            backup_path.write_text(existing_content, encoding="utf-8")

    was_empty = existing_content is None or existing_content.strip() == ""

    # Merge preservando estructura existente y otros hooks
    if not isinstance(config.get("hooks"), dict):
        config["hooks"] = {}
    if not isinstance(config["hooks"].get("UserPromptSubmit"), list):
        config["hooks"]["UserPromptSubmit"] = []
    config["hooks"]["UserPromptSubmit"].append(
        {
            "matcher": "",
            "hooks": [{"type": "command", "command": _pii_hook_command()}],
        }
    )

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return "created" if was_empty else "merged"


def _guard_hook_command() -> str:
    """Comando del hook de guardrails, pinneado al intérprete actual."""
    return _hook_command(GUARD_HOOK_MODULE)


def _guard_hook_already_registered(pre_tool_use: list) -> bool:
    """True si algún hook de PreToolUse ya invoca el módulo guard de forge."""
    for group in pre_tool_use:
        if not isinstance(group, dict):
            continue
        for hook in group.get("hooks", []) or []:
            if isinstance(hook, dict) and GUARD_HOOK_MODULE in str(hook.get("command", "")):
                return True
    return False


def register_guard_hook() -> str:
    """Registra el hook PreToolUse de guardrails en ~/.claude/settings.json (merge idempotente).

    Estructura diferente a UserPromptSubmit: PreToolUse usa matcher "Bash" a nivel de grupo.

    Returns:
        'present' — el hook ya estaba registrado, no se modificó nada
        'created' — settings.json no existía o estaba vacío, se creó con el hook
        'merged'  — settings.json existía con otra config, se hizo merge
    """
    settings_path = CLAUDE_HOME / "settings.json"

    existing_content: str | None = None
    config: dict = {}
    if settings_path.exists():
        try:
            existing_content = settings_path.read_text(encoding="utf-8")
            config = json.loads(existing_content) or {}
            if not isinstance(config, dict):
                config = {}
        except (json.JSONDecodeError, OSError):
            config = {}

    # Idempotencia: si el hook guard ya existe, no tocar nada
    hooks = config.get("hooks")
    if isinstance(hooks, dict):
        ptu = hooks.get("PreToolUse")
        if isinstance(ptu, list) and _guard_hook_already_registered(ptu):
            return "present"

    # Backup antes de escribir — solo si aún no existe (preserva pristine de run())
    if existing_content is not None:
        backup_path = settings_path.with_suffix(".json.forge-bak")
        if not backup_path.exists():
            with contextlib.suppress(OSError):
                backup_path.write_text(existing_content, encoding="utf-8")

    was_empty = existing_content is None or existing_content.strip() == ""

    # Merge preservando estructura existente y otros hooks
    if not isinstance(config.get("hooks"), dict):
        config["hooks"] = {}
    if not isinstance(config["hooks"].get("PreToolUse"), list):
        config["hooks"]["PreToolUse"] = []
    config["hooks"]["PreToolUse"].append(
        {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": _guard_hook_command()}],
        }
    )

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return "created" if was_empty else "merged"


def install_global_claude_md() -> str:
    """Instala el institucional como `~/.claude/CLAUDE.md` (doctrina global del orquestador).

    forge es la fuente de la doctrina del orquestador, así que el institucional ES el
    CLAUDE.md global. Antes de pisar un archivo distinto del usuario, lo respalda en
    `backup/forge/<timestamp>/` (fuera del path de carga de Claude Code, para no confundir
    al modelo con dos CLAUDE.md). Si el contenido ya es idéntico, no toca nada — idempotente,
    sin proliferación de backups.

    Returns:
        'present'  — el global ya era idéntico al institucional, no se tocó nada
        'created'  — no existía `~/.claude/CLAUDE.md`, se creó
        'replaced' — existía contenido distinto: se respaldó y se reemplazó
    """
    new_content = (
        get_share_root() / "templates" / "CLAUDE-md-institucional.md"
    ).read_text(encoding="utf-8")
    target = CLAUDE_HOME / "CLAUDE.md"

    if target.exists():
        current = target.read_text(encoding="utf-8")
        if current == new_content:
            return "present"
        # Microsegundos (%f) para que dos backups en el mismo segundo no colisionen.
        ts = datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
        backup_dir = CLAUDE_HOME / "backup" / "forge" / ts
        backup_dir.mkdir(parents=True, exist_ok=True)
        (backup_dir / "CLAUDE.md").write_text(current, encoding="utf-8")
        status = "replaced"
    else:
        status = "created"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_content, encoding="utf-8")
    return status


def prompt_context7_yn() -> str:
    """Muestra el prompt de registro de Context7 y lee la respuesta y/N.

    Default: registrar (Y). En entorno no-interactivo (stdin no es tty) retorna 'y'
    sin mostrar prompt ni llamar a input(), para no colgar en CI.

    Returns:
        'y' — registrar (incluyendo default por enter vacío y entornos no-interactivos)
        'n' — no registrar
    """
    # Entorno no-interactivo/CI: no colgar, registrar por defecto
    if not sys.stdin.isatty():
        return "y"

    response = input(PROMPT_CONTEXT7_TEXT).strip().lower()
    # Default Y: vacío o afirmativo
    if response in {"", "y", "yes"}:
        return "y"
    return "n"


# =============================================================================
# === Frontmatter injection ===
# =============================================================================


def inject_no_invoke_frontmatter(content: str) -> str:
    """Inject (or merge) disable-model-invocation + user-invocable into YAML frontmatter.

    Idempotent. Preserves existing frontmatter keys; only adds/overwrites the
    two required keys. If no frontmatter, prepends one.

    Args:
        content: Raw markdown content of a skill file.

    Returns:
        Content with frontmatter containing the two required keys.
    """
    if content.startswith("---\n"):
        try:
            end = content.index("\n---\n", 4)
        except ValueError:
            # malformed frontmatter (no closing ---) — treat as no frontmatter
            return _prepend_frontmatter(content)
        fm_raw = content[4:end]
        body = content[end + len("\n---\n"):]
        try:
            fm = yaml.safe_load(fm_raw) or {}
            if not isinstance(fm, dict):
                fm = {}
        except yaml.YAMLError:
            fm = {}
        fm.update(_REQUIRED_FM_KEYS)
        new_fm = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip()
        return f"---\n{new_fm}\n---\n{body}"
    return _prepend_frontmatter(content)


def _prepend_frontmatter(content: str) -> str:
    """Prepend a fresh frontmatter block to content."""
    fm = yaml.safe_dump(_REQUIRED_FM_KEYS, sort_keys=False).rstrip()
    return f"---\n{fm}\n---\n\n{content}"


# =============================================================================
# === Asset deposit ===
# =============================================================================


def get_share_root() -> Path:
    """Return the package share root: sysconfig data_dir / share / forge."""
    return Path(sysconfig.get_path("data")) / "share" / "forge"


def install_assets() -> dict:
    """Deposit skills, agents, commands into ~/.claude/.

    Returns:
        Manifest dict with keys:
          skills_deposited: int
          shared_deposited: int
          agents_deposited: int
          commands_deposited: int
          warnings: list[str]
    """
    share = get_share_root()
    if not share.exists():
        raise SystemExit(EXIT_DEPOSIT_FAILED)

    skills_src = share / "skills"
    shared_src = skills_src / "_shared"
    agents_src = share / "agents"
    commands_src = share / "commands"
    claude_skills = CLAUDE_HOME / "skills"
    claude_agents = CLAUDE_HOME / "agents"
    claude_commands = CLAUDE_HOME / "commands"
    warnings: list[str] = []

    # 1. fg-*.md individual skills → <stem>/SKILL.md
    n_skills = _deposit_individual_skills(skills_src, claude_skills)

    # 2. _shared co-located companions (single-consumer, no frontmatter)
    _deposit_colocated(
        shared_src / "strict-tdd.md",
        claude_skills / "fg-implement" / "strict-tdd.md",
    )
    _deposit_colocated(
        shared_src / "strict-tdd-verify.md",
        claude_skills / "fg-review" / "strict-tdd-verify.md",
    )

    # 3. _shared cross-cutting → forge-shared/<name>/SKILL.md with frontmatter
    n_shared = _deposit_shared_skills(shared_src, claude_skills)

    # 4. agents → flat copy
    n_agents = _deposit_agents(agents_src, claude_agents)

    # 5. commands → flat copy
    n_commands = _deposit_commands(commands_src, claude_commands)

    return {
        "skills_deposited": n_skills,
        "shared_deposited": n_shared,
        "agents_deposited": n_agents,
        "commands_deposited": n_commands,
        "warnings": warnings,
    }


def _deposit_individual_skills(skills_src: Path, claude_skills: Path) -> int:
    """Copy fg-*.md files to <claude_skills>/<stem>/SKILL.md with no-invoke frontmatter."""
    count = 0
    for md in sorted(skills_src.glob("fg-*.md")):
        dest_dir = claude_skills / md.stem
        dest_dir.mkdir(parents=True, exist_ok=True)
        injected = inject_no_invoke_frontmatter(md.read_text(encoding="utf-8"))
        (dest_dir / "SKILL.md").write_text(injected, encoding="utf-8")
        count += 1
    return count


def _deposit_shared_skills(shared_src: Path, claude_skills: Path) -> int:
    """Copy cross-cutting _shared files to forge-shared/<name>/SKILL.md with frontmatter."""
    count = 0
    for md in sorted(shared_src.glob("*.md")):
        if md.stem not in _CROSS_CUTTING:
            continue  # strict-tdd* are co-located; skip them here
        dest_dir = claude_skills / "forge-shared" / md.stem
        dest_dir.mkdir(parents=True, exist_ok=True)
        injected = inject_no_invoke_frontmatter(md.read_text(encoding="utf-8"))
        (dest_dir / "SKILL.md").write_text(injected, encoding="utf-8")
        count += 1
    return count


def _deposit_colocated(src: Path, dest: Path) -> bool:
    """Copy a single co-located companion file if source exists."""
    if not src.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def _deposit_agents(agents_src: Path, claude_agents: Path) -> int:
    """Copy agent .md files flat into claude_agents/."""
    if not agents_src.exists():
        return 0
    claude_agents.mkdir(parents=True, exist_ok=True)
    count = 0
    for md in sorted(agents_src.glob("*.md")):
        shutil.copy2(md, claude_agents / md.name)
        count += 1
    return count


def _deposit_commands(commands_src: Path, claude_commands: Path) -> int:
    """Copia archivos fg-*.md de commands al directorio global de commands."""
    if not commands_src.exists():
        return 0
    claude_commands.mkdir(parents=True, exist_ok=True)
    count = 0
    for md in sorted(commands_src.glob("fg-*.md")):
        shutil.copy2(md, claude_commands / md.name)
        count += 1
    return count


# =============================================================================
# === Engram install ===
# =============================================================================


def _detect_platform() -> tuple[str, str]:
    """Detect OS and arch tokens for GitHub Release asset naming.

    Returns:
        (os_token, arch_token) where tokens match engram release naming.

    Raises:
        SystemExit(EXIT_PLATFORM_UNSUPPORTED) if platform is not supported.
    """
    plat = sys.platform  # 'linux', 'darwin', 'win32'
    mach = platform.machine().lower()  # 'x86_64', 'amd64', 'arm64', 'aarch64'
    os_map = {"linux": "linux", "darwin": "darwin", "win32": "windows"}
    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    if plat not in os_map or mach not in arch_map:
        raise SystemExit(EXIT_PLATFORM_UNSUPPORTED)
    return os_map[plat], arch_map[mach]


def _download_binary(url: str, dest: Path) -> None:
    """Download binary from url to dest. Retries once on failure.

    Args:
        url: Direct download URL of the asset.
        dest: Target path (parent directory is created if missing).

    Raises:
        urllib.error.URLError | OSError: after 2 failed attempts.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_exc: Exception | None = None
    for _attempt in (1, 2):
        try:
            urllib.request.urlretrieve(url, str(dest))
            return
        except (urllib.error.URLError, OSError) as exc:
            last_exc = exc
    raise last_exc  # type: ignore[misc]


def _edit_path_unix(bin_dir: Path) -> dict[str, str]:
    """Append PATH export to ~/.bashrc, ~/.zshrc, and ~/.profile (Unix / macOS).

    Edits all three rc files that EXIST. If a file does not exist, it is
    skipped (not created) — except ~/.profile which is always created if
    none of the other files existed. Idempotent: no duplicate entries.

    Returns:
        dict mapping rc filename (e.g. '.bashrc') to one of:
            'present'  — entry was already there
            'appended' — entry was added to existing file
            'created'  — file was created with the entry (only ~/.profile)
            'skipped'  — file did not exist (only for .bashrc / .zshrc)

    Q4 (resolved in apply): print_report advises to open a new terminal
    for PATH propagation on Unix (same UX as Windows).
    REQ-PLATFORM-03: edit ~/.bashrc, ~/.zshrc, and ~/.profile.
    """
    home = Path.home()
    line = f'\n# Added by forge install\nexport PATH="{bin_dir}:$PATH"\n'
    rc_files = [".bashrc", ".zshrc", ".profile"]
    results: dict[str, str] = {}

    for rc_name in rc_files:
        rc_path = home / rc_name
        if not rc_path.exists():
            results[rc_name] = "skipped"
            continue
        existing = rc_path.read_text(encoding="utf-8")
        if str(bin_dir) in existing:
            results[rc_name] = "present"
            continue
        rc_path.write_text(existing + line, encoding="utf-8")
        results[rc_name] = "appended"

    # Ensure ~/.profile always exists (fallback for login shells)
    if results.get(".profile") == "skipped":
        profile = home / ".profile"
        profile.write_text(line.lstrip("\n"), encoding="utf-8")
        results[".profile"] = "created"

    return results


def _edit_path_windows(bin_dir: Path) -> str:
    """Edit HKCU\\Environment\\Path via winreg (Windows only).

    Returns:
        'present'  — already in PATH
        'appended' — added to PATH

    If SendMessage broadcast fails, prints a warning (non-fatal).
    """
    import ctypes
    import winreg  # type: ignore[import]

    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x1A
    SMTO_ABORTIFHUNG = 0x0002

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        "Environment",
        0,
        winreg.KEY_READ | winreg.KEY_WRITE,
    )
    try:
        current, _ = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        current = ""

    if str(bin_dir) in current.split(";"):
        winreg.CloseKey(key)
        return "present"

    new_val = f"{current};{bin_dir}" if current else str(bin_dir)
    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_val)
    winreg.CloseKey(key)

    try:
        ctypes.windll.user32.SendMessageTimeoutW(  # type: ignore[attr-defined]
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
            SMTO_ABORTIFHUNG, 5000, None,
        )
    except Exception:
        print("Abrí una nueva terminal para que el PATH se actualice.")

    return "appended"


def _xattr_cleanup_darwin(binary_path: Path) -> None:
    """Remove macOS quarantine attribute from binary (best-effort).

    Only runs on darwin. Failures are silently swallowed — the install
    continues without aborting.
    """
    if sys.platform != "darwin":
        return
    with contextlib.suppress(FileNotFoundError, subprocess.TimeoutExpired, OSError):
        subprocess.run(
            ["xattr", "-d", "com.apple.quarantine", str(binary_path)],
            capture_output=True,
            timeout=5,
            check=False,
        )


def register_engram_mcp(binary_path: Path | None = None) -> str:
    """Registra el bloque MCP de engram en ~/.claude.json con merge idempotente.

    Sigue el mismo patrón que register_codegraph_mcp() y register_context7_mcp():
    lee ~/.claude.json existente (o {} si ausente/corrupto), verifica idempotencia,
    crea backup .forge-bak antes de escribir y hace merge preservando el resto.

    Args:
        binary_path: ruta absoluta al binario de engram cuando se conoce (instalación
                     nueva). None o "engram" usa el nombre genérico como command
                     (depende del PATH del proceso que lo spawne).

    Returns:
        'present'  — el bloque ya existía y es válido, no se modificó nada
        'created'  — el archivo no existía o estaba vacío, se creó con el bloque
        'merged'   — el archivo existía con otra config, se hizo merge
    """
    claude_json_path = CODEGRAPH_CLAUDE_JSON  # ~/.claude.json — mismo archivo, sin duplicar path

    # Leer configuración existente
    existing_content: str | None = None
    config: dict = {}
    if claude_json_path.exists():
        try:
            existing_content = claude_json_path.read_text(encoding="utf-8")
            config = json.loads(existing_content) or {}
            if not isinstance(config, dict):
                config = {}
        except (json.JSONDecodeError, OSError):
            config = {}

    # Idempotencia: si el bloque ya existe y es válido, no tocar nada
    mcp_servers = config.get("mcpServers", {})
    if isinstance(mcp_servers, dict) and "engram" in mcp_servers:
        return "present"

    # Crear backup antes de escribir — solo si aún no existe (preserva pristine de run())
    if existing_content is not None:
        backup_path = claude_json_path.with_suffix(".json.forge-bak")
        if not backup_path.exists():
            with contextlib.suppress(OSError):
                backup_path.write_text(existing_content, encoding="utf-8")

    # Construir el bloque: ruta absoluta si la conocemos, "engram" como fallback
    command = str(binary_path) if binary_path is not None else "engram"
    block = {
        "type": "stdio",
        "command": command,
        "args": list(_ENGRAM_MCP_ARGS),
    }

    # Merge: agregar mcpServers.engram preservando el resto
    if "mcpServers" not in config or not isinstance(config.get("mcpServers"), dict):
        config["mcpServers"] = {}
    config["mcpServers"]["engram"] = block

    # Determinar status antes de escribir
    was_empty = existing_content is None or existing_content.strip() == ""

    claude_json_path.parent.mkdir(parents=True, exist_ok=True)
    claude_json_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return "created" if was_empty else "merged"


def install_engram() -> tuple[bool, str]:
    """Download and install engram binary. Edits PATH, registers MCP.

    Q1 (resolved in apply): GitHub assets are tarballs:
      engram_{version}_{os}_{arch}.tar.gz (Unix) or .zip (Windows).
    Asset selection: match first asset whose name starts with
      'engram_' and ends with '{os_token}_{arch_token}.tar.gz' (or .zip).
    Binary is extracted from archive.

    Returns:
        (True, message)  — success
        (False, message) — download or extraction failed
    """
    import tarfile
    import tempfile
    import zipfile

    try:
        os_tok, arch_tok = _detect_platform()
    except SystemExit:
        return False, f"Plataforma no soportada: {sys.platform}/{platform.machine()}"

    ext = ".zip" if os_tok == "windows" else ".tar.gz"
    expected_suffix = f"{os_tok}_{arch_tok}{ext}"

    # Fetch release metadata
    try:
        with urllib.request.urlopen(GITHUB_RELEASES_API, timeout=15) as resp:
            release = json.loads(resp.read())
    except (urllib.error.URLError, OSError) as exc:
        return False, f"No se pudo obtener la release de engram: {exc}"

    assets = release.get("assets", [])
    asset = next(
        (a for a in assets if a["name"].endswith(expected_suffix)),
        None,
    )
    if asset is None:
        available = [a["name"] for a in assets]
        return False, (
            f"Asset no encontrado para {os_tok}/{arch_tok}. "
            f"Assets disponibles: {available}"
        )

    download_url = asset["browser_download_url"]

    # Choose destination
    bin_dir = ENGRAM_BIN_DIR_WIN if os_tok == "windows" else ENGRAM_BIN_DIR_UNIX
    bin_name = "engram.exe" if os_tok == "windows" else "engram"
    binary_dest = bin_dir / bin_name

    # Download to temp file then extract
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path_str = tmp.name

        _download_binary(download_url, Path(tmp_path_str))

        binary_dest.parent.mkdir(parents=True, exist_ok=True)

        if ext == ".tar.gz":
            with tarfile.open(tmp_path_str, "r:gz") as tf:
                # Find engram binary inside archive
                member = next(
                    (m for m in tf.getmembers()
                     if m.name.endswith("engram") or m.name.endswith("engram.exe")),
                    None,
                )
                if member is None:
                    return False, "Binary 'engram' not found inside tarball."
                member.name = bin_name  # flatten path
                # filter="data" hardens against symlink attacks (Python 3.12+).
                if sys.version_info >= (3, 12):
                    tf.extract(member, path=str(binary_dest.parent), filter="data")
                else:
                    tf.extract(member, path=str(binary_dest.parent))
        else:
            with zipfile.ZipFile(tmp_path_str, "r") as zf:
                member = next(
                    (n for n in zf.namelist()
                     if n.endswith("engram") or n.endswith("engram.exe")),
                    None,
                )
                if member is None:
                    return False, "Binary 'engram' not found inside zip."
                with zf.open(member) as src, open(binary_dest, "wb") as dst:
                    dst.write(src.read())

        os.unlink(tmp_path_str)

    except (urllib.error.URLError, OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        return False, f"Error descargando/extrayendo engram: {exc}"

    # chmod +x on Unix
    if os_tok != "windows":
        os.chmod(binary_dest, 0o755)

    # macOS quarantine cleanup (best-effort)
    _xattr_cleanup_darwin(binary_dest)

    # Edit PATH
    if os_tok == "windows":
        _edit_path_windows(bin_dir)
    else:
        _edit_path_unix(bin_dir)

    # Register MCP — absolute path known here, more robust than relying on PATH for MCP spawning
    register_engram_mcp(binary_dest)

    return True, f"engram instalado en {binary_dest}"


# =============================================================================
# === Runner ===
# =============================================================================


def prompt_user_yn() -> str:
    """Display engram install prompt and read y/n response.

    Accepts: y, Y, yes, YES (case-insensitive) as affirmative.
    Any other input is treated as 'n'.

    Returns:
        'y' or 'n'
    """
    response = input(PROMPT_TEXT).strip().lower()
    return "y" if response in {"y", "yes"} else "n"


def print_report(report: dict) -> None:
    """Print human-readable install summary.

    Q4 (resolved in apply): always suggests opening a new terminal
    for PATH propagation on Unix (consistent with Windows UX).
    """
    engram_info = report.get("engram", {})
    assets = report.get("assets", {})
    codegraph_info = report.get("codegraph", {})
    context7_info = report.get("context7", {})
    pii_info = report.get("pii_hook", {})
    claude_md_info = report.get("claude_md", {})

    print("\nforge install — resumen\n")

    if engram_info.get("mcp_json"):
        print(f"  engram: detectado vía ~/.claude.json mcpServers ({engram_info['mcp_json']})")
    elif engram_info.get("which"):
        print(f"  engram: detectado en PATH ({engram_info['which']})")
    elif engram_info.get("version_check"):
        print(f"  engram: detectado vía --version ({engram_info['version_check']})")
    elif engram_info.get("installed"):
        print(f"  engram: instalado en {engram_info['installed']}")
    else:
        print("  engram: no detectado (salteado por flag)")

    # Sección CodeGraph
    if codegraph_info:
        cg_status = codegraph_info.get("status", "")
        cg_msg = codegraph_info.get("msg", "")
        if cg_status == "already_present":
            print(f"  codegraph: ya instalado ({cg_msg})")
        elif cg_status == "installed":
            print(f"  codegraph: instalado — {cg_msg}")
        elif cg_status == "skipped":
            print(f"  codegraph: omitido ({cg_msg})")
        elif cg_status == "failed":
            print(f"  codegraph: fallo en instalación — {cg_msg}")
        elif cg_status == "mcp_only":
            print(f"  codegraph: MCP registrado — {cg_msg}")
        else:
            print(f"  codegraph: {cg_msg}")

    # Sección Context7
    if context7_info:
        ctx_status = context7_info.get("status", "")
        ctx_msg = context7_info.get("msg", "")
        ctx_mcp = context7_info.get("mcp", "")
        if ctx_status == "registered":
            suffix = f" ({ctx_mcp})" if ctx_mcp else ""
            print(f"  context7: MCP registrado{suffix}")
        elif ctx_status == "skipped":
            print(f"  context7: omitido ({ctx_msg})")
        elif ctx_status == "failed":
            print(f"  context7: fallo en registro — {ctx_msg}")
        else:
            print(f"  context7: {ctx_msg}")

    # Sección CLAUDE.md global
    if claude_md_info:
        cm_status = claude_md_info.get("status", "")
        cm_msg = claude_md_info.get("msg", "")
        if cm_status == "created":
            print("  CLAUDE.md global: creado en ~/.claude/CLAUDE.md")
        elif cm_status == "replaced":
            print("  CLAUDE.md global: reemplazado (backup en ~/.claude/backup/forge/)")
        elif cm_status == "present":
            print("  CLAUDE.md global: ya actualizado (sin cambios)")
        elif cm_status == "failed":
            print(f"  CLAUDE.md global: fallo — {cm_msg}")

    # Sección Hook PII
    if pii_info:
        ph_status = pii_info.get("status", "")
        ph_hook = pii_info.get("hook", "")
        ph_msg = pii_info.get("msg", "")
        if ph_status == "registered":
            print(f"  hook PII: registrado en ~/.claude/settings.json ({ph_hook})")
        elif ph_status == "skipped":
            print(f"  hook PII: omitido ({ph_msg})")
        elif ph_status == "failed":
            print(f"  hook PII: fallo en registro — {ph_msg}")
        else:
            print(f"  hook PII: {ph_msg}")

    # Sección Hook Guardrails
    guard_hook_info = report.get("guard_hook", {})
    if guard_hook_info:
        gh_status = guard_hook_info.get("status", "")
        gh_hook = guard_hook_info.get("hook", "")
        gh_msg = guard_hook_info.get("msg", "")
        if gh_status == "registered":
            print(f"  hook guardrails: registrado en ~/.claude/settings.json ({gh_hook})")
        elif gh_status == "skipped":
            print(f"  hook guardrails: omitido ({gh_msg})")
        elif gh_status == "failed":
            print(f"  hook guardrails: fallo en registro — {gh_msg}")
        else:
            print(f"  hook guardrails: {gh_msg}")

    print(f"  skills depositadas: {assets.get('skills_deposited', 0)}")
    print(f"  shared (forge-shared): {assets.get('shared_deposited', 0)}")
    print(f"  agents depositados: {assets.get('agents_deposited', 0)}")
    print(f"  commands depositados: {assets.get('commands_deposited', 0)}")

    warnings = assets.get("warnings", [])
    if warnings:
        print("\n  Advertencias:")
        for w in warnings:
            print(f"    - {w}")

    print()
    print("  Para que el cambio de PATH surta efecto, abrí una nueva terminal.")
    print()
    print(POST_INSTALL_MESSAGE)


def run(args) -> int:  # args: argparse.Namespace
    """Orchestrate forge install. Returns exit code.

    Flow:
      1. detected, info = detect_engram()
      2. if not detected: install/skip/prompt engram
      3. Paso CodeGraph (try/except amplio — fallo NO aborta ni cambia exit code):
         - detect_codegraph() → si ya está, reportar y registrar MCP
         - --skip-codegraph → omitir
         - --install-codegraph → instalar sin prompt
         - else → prompt_codegraph_yn()
      4. manifest = install_assets()
      5. print_report(...)
      6. return EXIT_OK

    REQ-FLAGS-02: --install-engram wins over --skip-engram-check.
    REQ-FLAGS-03: if detected + --install-engram → log and skip reinstall.
    R-INST-04: --skip-codegraph omite instalación; --install-codegraph fuerza sin prompt.
    R-INST-05: fallo de CodeGraph → warning en reporte, NO cambia exit code.
    """
    # Snapshot both config files BEFORE any registrar mutates them — Fix 3 (pristine backup).
    # All registrars that write these files share this set via _backup_once() so that only
    # the first write per file within this run produces a backup.
    _run_backed_up: set = set()

    detected, info = detect_engram()

    if detected and getattr(args, "install_engram", False):
        # REQ-FLAGS-03: already detected, skip reinstall
        method = info.get("mcp_json") or info.get("which") or info.get("version_check") or "?"
        print(f"engram ya detectado vía {method}, salteando install")

        # Fix 1: detected but MCP block may still be missing — register if so.
        if not info.get("mcp_json"):
            detected_bin = info.get("which")
            _backup_once(CODEGRAPH_CLAUDE_JSON, _run_backed_up)
            register_engram_mcp(Path(detected_bin) if detected_bin else None)

    elif detected:
        # Detected (no --install-engram flag). Fix 1: if MCP block is missing, write it now.
        if not info.get("mcp_json"):
            detected_bin = info.get("which")
            _backup_once(CODEGRAPH_CLAUDE_JSON, _run_backed_up)
            register_engram_mcp(Path(detected_bin) if detected_bin else None)

    elif not detected:
        if getattr(args, "install_engram", False):
            # --install-engram takes precedence (REQ-FLAGS-02)
            ok, msg = install_engram()
            if not ok:
                sys.stderr.write(f"Error instalando engram: {msg}\n")
                return EXIT_ENGRAM_INSTALL_FAILED
            info["installed"] = msg

        elif getattr(args, "skip_engram_check", False):
            # --skip-engram-check: proceed to deposit without engram
            print("Advertencia: engram no detectado. Salteando check por --skip-engram-check.")

        else:
            # Interactive prompt
            answer = prompt_user_yn()
            if answer != "y":
                print("Instalá engram por tu cuenta y volvé a correr 'forge install'")
                return EXIT_ABORTED
            ok, msg = install_engram()
            if not ok:
                sys.stderr.write(f"Error instalando engram: {msg}\n")
                return EXIT_ENGRAM_INSTALL_FAILED
            info["installed"] = msg

    # Paso CodeGraph — try/except amplio: fallo no aborta ni cambia exit code (R-INST-05)
    codegraph_report: dict = {}
    try:
        if getattr(args, "skip_codegraph", False):
            codegraph_report = {"status": "skipped", "msg": "omitido por --skip-codegraph"}
        else:
            cg_detected, cg_info = detect_codegraph()

            if cg_detected:
                # Ya instalado — solo verificar/registrar MCP
                _backup_once(CODEGRAPH_CLAUDE_JSON, _run_backed_up)  # Fix 3
                mcp_status = register_codegraph_mcp()
                which_path = cg_info.get("which", "")
                codegraph_report = {"status": "already_present", "msg": which_path}
                if mcp_status == "created" or mcp_status == "merged":
                    codegraph_report["mcp"] = mcp_status

            else:
                # No instalado — determinar si instalar
                do_install: bool
                if getattr(args, "install_codegraph", False):
                    # --install-codegraph: sin prompt (CI-safe)
                    do_install = True
                else:
                    answer_cg = prompt_codegraph_yn()
                    do_install = answer_cg == "y"

                if do_install:
                    ok_cg, msg_cg = install_codegraph()
                    if ok_cg:
                        _backup_once(CODEGRAPH_CLAUDE_JSON, _run_backed_up)  # Fix 3
                        mcp_status = register_codegraph_mcp()
                        codegraph_report = {"status": "installed", "msg": msg_cg, "mcp": mcp_status}
                    else:
                        codegraph_report = {"status": "failed", "msg": msg_cg}
                else:
                    codegraph_report = {"status": "skipped", "msg": "omitido por elección del usuario"}

    except Exception as exc:  # noqa: BLE001 — defensa en profundidad R-INST-05
        codegraph_report = {"status": "failed", "msg": f"error inesperado: {exc}"}

    # Paso Context7 — try/except amplio: fallo no aborta ni cambia exit code (R-CTX-05)
    context7_report: dict = {}
    try:
        if getattr(args, "skip_context7", False):
            context7_report = {"status": "skipped", "msg": "omitido por --skip-context7"}
        else:
            if getattr(args, "install_context7", False):
                # --install-context7: sin prompt (CI-safe)
                _backup_once(CODEGRAPH_CLAUDE_JSON, _run_backed_up)  # Fix 3
                mcp_status_ctx = register_context7_mcp()
                context7_report = {"status": "registered", "mcp": mcp_status_ctx}
            else:
                answer_ctx = prompt_context7_yn()
                if answer_ctx == "y":
                    _backup_once(CODEGRAPH_CLAUDE_JSON, _run_backed_up)  # Fix 3
                    mcp_status_ctx = register_context7_mcp()
                    context7_report = {"status": "registered", "mcp": mcp_status_ctx}
                else:
                    context7_report = {"status": "skipped", "msg": "omitido por elección del usuario"}

    except Exception as exc:  # noqa: BLE001 — defensa en profundidad R-CTX-05
        context7_report = {"status": "failed", "msg": f"error inesperado: {exc}"}

    # Paso Hook PII — try/except amplio: fallo no aborta ni cambia exit code (fail-open)
    pii_hook_report: dict = {}
    _settings_path = CLAUDE_HOME / "settings.json"
    try:
        if getattr(args, "skip_pii_hook", False):
            pii_hook_report = {"status": "skipped", "msg": "omitido por --skip-pii-hook"}
        else:
            _backup_once(_settings_path, _run_backed_up)  # Fix 3
            hook_status = register_pii_hook()
            pii_hook_report = {"status": "registered", "hook": hook_status}
    except Exception as exc:  # noqa: BLE001 — defensa en profundidad (fail-open)
        pii_hook_report = {"status": "failed", "msg": f"error inesperado: {exc}"}

    # Paso Hook guardrails — try/except amplio: fallo no aborta ni cambia exit code (fail-open)
    guard_hook_report: dict = {}
    try:
        if getattr(args, "skip_guard_hook", False):
            guard_hook_report = {"status": "skipped", "msg": "omitido por --skip-guard-hook"}
        else:
            _backup_once(_settings_path, _run_backed_up)  # Fix 3 (no-op if pii already backed up)
            hook_status = register_guard_hook()
            guard_hook_report = {"status": "registered", "hook": hook_status}
    except Exception as exc:  # noqa: BLE001 — defensa en profundidad (fail-open)
        guard_hook_report = {"status": "failed", "msg": f"error inesperado: {exc}"}

    # Paso CLAUDE.md global (doctrina del orquestador) — fail-open
    claude_md_report: dict = {}
    try:
        cm_status = install_global_claude_md()
        claude_md_report = {"status": cm_status}
    except Exception as exc:  # noqa: BLE001 — fail-open
        claude_md_report = {"status": "failed", "msg": f"error inesperado: {exc}"}

    # Deposit skills and agents
    manifest = install_assets()
    print_report({
        "engram": info,
        "assets": manifest,
        "codegraph": codegraph_report,
        "context7": context7_report,
        "pii_hook": pii_hook_report,
        "guard_hook": guard_hook_report,
        "claude_md": claude_md_report,
    })
    return EXIT_OK
