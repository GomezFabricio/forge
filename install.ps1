# forge — instalador rápido (Windows / PowerShell)
#
# Uso:
#   iwr https://github.com/GomezFabricio/forge/raw/main/install.ps1 -useb | iex
#
# Hace tres cosas: verifica Python 3.10+, asegura pipx, instala forge en un
# entorno aislado y deposita las skills, agents y el hook PII en ~/.claude/.
#
# Variables de entorno:
#   FORGE_REPO_URL   override del origen de instalación (default: git+main).
#
# Cualquier argumento extra se pasa tal cual a `forge install`
# (ej: --skip-context7, --install-codegraph, --skip-pii-hook).
#
# IMPORTANTE: fijamos 'Continue' EXPLÍCITAMENTE. En Windows PowerShell 5.1, cuando
# un ejecutable nativo (python/pip/pipx) escribe en stderr, PowerShell envuelve esa
# salida en un `NativeCommandError`; con `$ErrorActionPreference = 'Stop'` eso se
# vuelve terminante y aborta el script aunque el comando haya sido exitoso (pip y
# pipx escriben avisos normales en stderr). Al invocarse vía `iwr ... | iex`, el
# script corre en el scope de la sesión y HEREDA su ErrorActionPreference, así que
# no alcanza con "no ponerlo en Stop": hay que forzarlo a 'Continue'. Los fallos
# reales se detectan verificando `$LASTEXITCODE` después de cada comando nativo.
$ErrorActionPreference = 'Continue'

$RepoUrl = if ($env:FORGE_REPO_URL) {
    $env:FORGE_REPO_URL
} else {
    'git+https://github.com/GomezFabricio/forge.git'
}

function Write-Step($msg) { Write-Host "forge install: $msg" }
function Stop-Install($msg) { Write-Host "forge install: $msg" -ForegroundColor Red; exit 1 }

# 1. Verificar Python 3.10+
$python = $null
foreach ($candidate in @('python', 'python3')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        & $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
    }
}
if (-not $python) {
    Write-Step 'forge necesita Python 3.10 o superior y no encontré una versión compatible.'
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Step 'Instalalo con:  winget install -e --id Python.Python.3.13'
    } else {
        Write-Step 'Bajá el instalador desde https://www.python.org/downloads/windows/ y tildá "Add python.exe to PATH".'
    }
    Write-Step '(Ojo: el "python" del Microsoft Store es un stub que no sirve para instalar paquetes; usá winget o python.org.)'
    Stop-Install 'cuando lo tengas, abrí una terminal nueva y volvé a correr este instalador.'
}

# 2. Asegurar pipx. Detectamos con `find_spec` (no imprime nada) en vez de
#    `python -m pipx --version`, que escupe "No module named pipx" a stderr.
& $python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('pipx') else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Step 'pipx no encontrado — instalando con pip --user...'
    & $python -m pip install --user pipx
    if ($LASTEXITCODE -ne 0) {
        Stop-Install 'no se pudo instalar pipx con pip. Revisá tu instalación de Python.'
    }
    & $python -m pipx ensurepath *> $null
}

# 3. Instalar forge (--force reinstala/upgradea de forma idempotente)
Write-Step "instalando forge desde $RepoUrl ..."
& $python -m pipx install --force $RepoUrl
if ($LASTEXITCODE -ne 0) {
    Stop-Install "pipx no pudo instalar forge desde $RepoUrl."
}

# 4. Depositar assets en ~/.claude/ (pipx deja el shim en %USERPROFILE%\.local\bin,
#    que puede no estar en el PATH de esta sesión recién instalado pipx)
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
Write-Step 'depositando skills, agents y hook PII en ~/.claude/ ...'
forge install @args
if ($LASTEXITCODE -ne 0) {
    Stop-Install "'forge install' falló. Revisá el mensaje de arriba."
}

Write-Step "listo. Si el PATH no tomó 'forge', abrí una nueva terminal."
