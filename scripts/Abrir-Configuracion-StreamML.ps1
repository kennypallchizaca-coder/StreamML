$ErrorActionPreference = 'Stop'

# This is the only bootstrap entry point.  It creates an isolated environment
# and installs the local assistant without asking the operator to type commands.
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$environmentPath = Join-Path $repositoryRoot '.venv-setup'
$python = Join-Path $environmentPath 'Scripts\python.exe'
$setup = Join-Path $environmentPath 'Scripts\streamml-setup.exe'

if (-not (Test-Path -LiteralPath $python)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) {
        throw 'No se encontró Python. Instala Python 3.11 o posterior desde python.org y vuelve a abrir este archivo.'
    }
    & py -3.11 -m venv $environmentPath
}

& $python -m pip install --disable-pip-version-check --upgrade pip
& $python -m pip install --disable-pip-version-check -e (Join-Path $repositoryRoot 'apps\connector')

if (-not (Test-Path -LiteralPath $setup)) {
    throw 'La instalación del asistente local no se completó.'
}

Start-Process -FilePath $setup -WorkingDirectory $repositoryRoot -WindowStyle Hidden
Write-Host 'El asistente de StreamML se abrió en el navegador. Puedes cerrar esta ventana.'
