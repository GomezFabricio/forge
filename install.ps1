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

$ErrorActionPreference = 'Stop'

$RepoUrl = if ($env:FORGE_REPO_URL) {
    $env:FORGE_REPO_URL
} else {
    'git+https://github.com/GomezFabricio/forge.git'
}

function Write-Step($msg) { Write-Host "forge install: $msg" }

# 1. Verificar Python 3.10+
$python = $null
foreach ($candidate in @('python', 'python3')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        & $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
    }
}
if (-not $python) {
    Write-Error 'forge install: se requiere Python 3.10 o superior. Instalalo y volvé a correr.'
    exit 1
}

# 2. Asegurar pipx (lo invocamos vía módulo para no depender del PATH de esta sesión)
& $python -m pipx --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Step 'pipx no encontrado — instalando con pip --user...'
    & $python -m pip install --user pipx
    & $python -m pipx ensurepath
}

# 3. Instalar forge (--force reinstala/upgradea de forma idempotente)
Write-Step "instalando forge desde $RepoUrl ..."
& $python -m pipx install --force $RepoUrl

# 4. Depositar assets en ~/.claude/ (pipx deja el shim en %USERPROFILE%\.local\bin,
#    que puede no estar en el PATH de esta sesión recién instalado pipx)
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
Write-Step 'depositando skills, agents y hook PII en ~/.claude/ ...'
forge install @args

Write-Step "listo. Si el PATH no tomó 'forge', abrí una nueva terminal."
