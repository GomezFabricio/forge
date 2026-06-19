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
# Nota: NO usamos `$ErrorActionPreference = 'Stop'` de forma global. En Windows
# PowerShell 5.1, cuando un ejecutable nativo (python/pip/pipx) escribe en stderr,
# PowerShell envuelve esa salida en un `NativeCommandError` terminante. Como pip y
# pipx escriben avisos normales en stderr, con 'Stop' el script abortaría en
# operaciones que en realidad fueron exitosas. En su lugar verificamos
# `$LASTEXITCODE` después de cada paso, que es la forma fiable de detectar fallos
# de comandos nativos.

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
    Stop-Install 'se requiere Python 3.10 o superior. Instalalo y volvé a correr.'
}

# 2. Asegurar pipx (lo invocamos vía módulo para no depender del PATH de esta sesión)
& $python -m pipx --version *> $null
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
