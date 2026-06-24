#!/usr/bin/env bash
# forge — instalador rápido (Linux / macOS)
#
# Uso:
#   curl -sSL https://github.com/GomezFabricio/forge/raw/main/install.sh | bash
#
# Hace tres cosas: verifica Python 3.10+, asegura pipx, instala forge en un
# entorno aislado y deposita las skills, agents y el hook PII en ~/.claude/.
#
# Variables de entorno:
#   FORGE_REPO_URL   override del origen de instalación (default: git+main).
#
# Cualquier argumento extra se pasa tal cual a `forge install`
# (ej: --skip-context7, --install-codegraph, --skip-pii-hook).
set -euo pipefail

REPO_URL="${FORGE_REPO_URL:-git+https://github.com/GomezFabricio/forge.git}"

log() { printf 'forge install: %s\n' "$1" >&2; }

# 1. Verificar Python 3.10+
PYTHON_BIN=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 \
     && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  log "forge necesita Python 3.10 o superior y no encontré una versión compatible."
  case "$(uname -s)" in
    Darwin)
      if command -v brew >/dev/null 2>&1; then
        log "Instalalo con:  brew install python@3.13"
      else
        log "Instalá Homebrew (https://brew.sh) y luego:  brew install python@3.13"
        log "O bajá el instalador desde https://www.python.org/downloads/macos/"
      fi
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        log "Instalalo con:  sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
      elif command -v dnf >/dev/null 2>&1; then
        log "Instalalo con:  sudo dnf install -y python3 python3-pip"
      elif command -v pacman >/dev/null 2>&1; then
        log "Instalalo con:  sudo pacman -S --needed python python-pip"
      elif command -v zypper >/dev/null 2>&1; then
        log "Instalalo con:  sudo zypper install -y python3 python3-pip"
      else
        log "Instalá Python 3.10+ con el gestor de paquetes de tu distro, o desde https://www.python.org/downloads/"
      fi
      ;;
    *)
      log "Instalá Python 3.10+ desde https://www.python.org/downloads/"
      ;;
  esac
  log "Cuando lo tengas, volvé a correr este instalador."
  exit 1
fi

# 2. Asegurar pipx (lo invocamos vía módulo para no depender del PATH de esta sesión)
if ! "$PYTHON_BIN" -m pipx --version >/dev/null 2>&1; then
  log "pipx no encontrado — instalando con pip --user..."
  # PEP 668: en distros con entorno "externally-managed" (Debian 12+, Ubuntu 23.04+,
  # Arch) el primer intento falla; reintentamos con --break-system-packages (pip 23+).
  "$PYTHON_BIN" -m pip install --user pipx \
    || "$PYTHON_BIN" -m pip install --user --break-system-packages pipx
  "$PYTHON_BIN" -m pipx ensurepath
fi

# 3. Instalar forge (--force reinstala/upgradea de forma idempotente)
log "instalando forge desde ${REPO_URL} ..."
"$PYTHON_BIN" -m pipx install --force "$REPO_URL"

# 4. Depositar assets en ~/.claude/ (pipx deja el binario en ~/.local/bin)
export PATH="${HOME}/.local/bin:${PATH}"
log "depositando skills, agents y hook PII en ~/.claude/ ..."
forge install "$@"

log "listo. Si el PATH no tomó 'forge', abrí una nueva terminal."
