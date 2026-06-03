"""forge install — global asset installer.

Orchestrates:
  1. detect_engram()       — check if engram is already available
  2. install_engram()      — download binary, edit PATH, register MCP (optional)
  3. install_assets()      — deposit skills, agents into ~/.claude/
  4. print_report()        — human-readable summary

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
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import urllib.error
import urllib.request
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
MCP_JSON_PATH = CLAUDE_HOME / "mcp" / "engram.json"
ENGRAM_BIN_DIR_UNIX = Path.home() / ".engram" / "bin"
ENGRAM_BIN_DIR_WIN = Path.home() / ".engram" / "bin"

GITHUB_RELEASES_API = (
    "https://api.github.com/repos/Gentleman-Programming/engram/releases/latest"
)

# Q1 (resolved in apply): assets are tarballs: engram_{ver}_{os}_{arch}.tar.gz
# Windows uses .zip. Binary is extracted from archive post-download.
# Naming: engram_{version}_{os}_{arch}[.tar.gz|.zip]
# OS tokens: linux, darwin, windows
# Arch tokens: amd64, arm64

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
  4. Registrar el MCP en ~/.claude/mcp/engram.json para que Claude
     Code lo levante automáticamente.

Si preferís instalarlo por tu cuenta (brew, pacman, manual), respondé N
y volvé a correr 'forge install' cuando lo tengas listo.

¿Lo instalo ahora? [y/N]: """

# Keys required in forge-shared SKILL.md files (non-invocable companions)
_REQUIRED_FM_KEYS: dict = {"disable-model-invocation": True, "user-invocable": False}

# Cross-cutting _shared files that go to forge-shared/ (with frontmatter injection)
_CROSS_CUTTING = {"skill-resolver", "engram-protocol", "fg-phase-common"}

# Orchestrator rule injection markers
ORCHESTRATOR_OPEN_MARKER = "<!-- forge:orchestrator -->"
ORCHESTRATOR_CLOSE_MARKER = "<!-- /forge:orchestrator -->"

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

    # Indicator 1: valid ~/.claude/mcp/engram.json pointing to existing binary
    if MCP_JSON_PATH.exists():
        try:
            data = json.loads(MCP_JSON_PATH.read_text(encoding="utf-8"))
            cmd = data.get("command")
            if cmd and Path(cmd).exists():
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
    """Deposit skills, agents into ~/.claude/.

    Returns:
        Manifest dict with keys:
          skills_deposited: int
          shared_deposited: int
          agents_deposited: int
          warnings: list[str]
    """
    share = get_share_root()
    if not share.exists():
        raise SystemExit(EXIT_DEPOSIT_FAILED)

    skills_src = share / "skills"
    shared_src = skills_src / "_shared"
    agents_src = share / "agents"
    claude_skills = CLAUDE_HOME / "skills"
    claude_agents = CLAUDE_HOME / "agents"
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

    return {
        "skills_deposited": n_skills,
        "shared_deposited": n_shared,
        "agents_deposited": n_agents,
        "warnings": warnings,
    }


def _deposit_individual_skills(skills_src: Path, claude_skills: Path) -> int:
    """Copy fg-*.md files to <claude_skills>/<stem>/SKILL.md."""
    count = 0
    for md in sorted(skills_src.glob("fg-*.md")):
        dest_dir = claude_skills / md.stem
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md, dest_dir / "SKILL.md")
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


def register_mcp(binary_path: Path) -> str:
    """Write (or overwrite) ~/.claude/mcp/engram.json with flat schema.

    Schema: {"command": "<abs_path>", "args": ["mcp", "--tools=agent"]}
    No mcpServers wrapper — forge is standalone.

    Returns:
        'created'    — file did not exist before
        'overwritten' — file existed and was replaced
    """
    MCP_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"command": str(binary_path), "args": ["mcp", "--tools=agent"]}
    existed = MCP_JSON_PATH.exists()
    MCP_JSON_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return "overwritten" if existed else "created"


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

    # Register MCP
    register_mcp(binary_dest)

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

    print("\nforge install — resumen\n")

    if engram_info.get("mcp_json"):
        print(f"  engram: detectado vía MCP JSON ({engram_info['mcp_json']})")
    elif engram_info.get("which"):
        print(f"  engram: detectado en PATH ({engram_info['which']})")
    elif engram_info.get("version_check"):
        print(f"  engram: detectado vía --version ({engram_info['version_check']})")
    elif engram_info.get("installed"):
        print(f"  engram: instalado en {engram_info['installed']}")
    else:
        print("  engram: no detectado (salteado por flag)")

    print(f"  skills depositadas: {assets.get('skills_deposited', 0)}")
    print(f"  shared (forge-shared): {assets.get('shared_deposited', 0)}")
    print(f"  agents depositados: {assets.get('agents_deposited', 0)}")

    warnings = assets.get("warnings", [])
    if warnings:
        print("\n  Advertencias:")
        for w in warnings:
            print(f"    - {w}")

    print()
    print("  Para que el cambio de PATH surta efecto, abrí una nueva terminal.")
    print()
    print("  Próximo paso: /fg-setup")


def run(args) -> int:  # args: argparse.Namespace
    """Orchestrate forge install. Returns exit code.

    Flow:
      1. detected, info = detect_engram()
      2. if not detected:
           if args.install_engram (wins over --skip):
               ok, msg = install_engram()
               if not ok: return EXIT_ENGRAM_INSTALL_FAILED
           elif args.skip_engram_check:
               proceed without engram install
           elif prompt_user_yn() == 'y':
               ok, msg = install_engram()
               if not ok: return EXIT_ENGRAM_INSTALL_FAILED
           else:
               print abort message; return EXIT_ABORTED
      3. manifest = install_assets()
      4. print_report(...)
      5. return EXIT_OK

    REQ-FLAGS-02: --install-engram wins over --skip-engram-check.
    REQ-FLAGS-03: if detected + --install-engram → log and skip reinstall.
    """
    detected, info = detect_engram()

    if detected and getattr(args, "install_engram", False):
        # REQ-FLAGS-03: already detected, skip reinstall
        method = info.get("mcp_json") or info.get("which") or info.get("version_check") or "?"
        print(f"engram ya detectado vía {method}, salteando install")

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

    # Deposit skills and agents
    manifest = install_assets()
    print_report({"engram": info, "assets": manifest})
    return EXIT_OK
