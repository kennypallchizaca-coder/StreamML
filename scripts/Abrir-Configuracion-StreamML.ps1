$ErrorActionPreference = 'Stop'

# This is the only bootstrap entry point.  It creates an isolated environment
# and installs the local assistant without asking the operator to type commands.
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$environmentPath = Join-Path $repositoryRoot '.venv-setup'
$python = Join-Path $environmentPath 'Scripts\python.exe'
$setup = Join-Path $environmentPath 'Scripts\streamml-setup.exe'
$connectorSource = Join-Path $repositoryRoot 'apps\connector'

# Never modify an environment that is currently loaded by the setup process.
# Reopening the launcher simply reuses the already-running local assistant.
$runningSetup = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -like "*$setup*" -or
            ($_.CommandLine -like '*streamml_connector.setup_ui*' -and $_.CommandLine -like "*$repositoryRoot*")
        )
    } |
    Select-Object -First 1
if ($runningSetup) {
    Write-Host 'El asistente de StreamML ya está abierto en http://127.0.0.1:8765/.'
    Write-Host 'Usa la ventana existente del navegador. Puedes cerrar esta ventana.'
    exit 0
}

if (-not (Test-Path -LiteralPath $python)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) {
        throw 'No se encontró Python. Instala Python 3.11 o posterior desde python.org y vuelve a abrir este archivo.'
    }
    & py -3.11 -m venv $environmentPath
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo crear el entorno aislado de StreamML.'
    }
}

$requiresRepair = -not (Test-Path -LiteralPath $setup)
if (-not $requiresRepair) {
    & $python -c "import streamml_connector, streamml_connector.setup_ui" 2>$null
    $requiresRepair = $LASTEXITCODE -ne 0
}

if ($requiresRepair) {
    Write-Host 'Instalando o reparando el asistente local de StreamML...'
    & $python -m pip install --disable-pip-version-check --force-reinstall -e $connectorSource
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo instalar el asistente local. Verifica tu conexión y vuelve a intentarlo.'
    }
}

if (-not (Test-Path -LiteralPath $setup)) {
    throw 'La instalación del asistente local no se completó.'
}

Start-Process -FilePath $setup -WorkingDirectory $repositoryRoot -WindowStyle Hidden
Write-Host 'El asistente de StreamML se abrió en el navegador. Puedes cerrar esta ventana.'
