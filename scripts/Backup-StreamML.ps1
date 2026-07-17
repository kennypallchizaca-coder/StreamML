param(
    [string]$EnvironmentFile = "deployment/.env",
    [string]$DestinationDirectory = "backups"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$composeFile = Join-Path $repositoryRoot "infrastructure/docker/docker-compose.yml"
$environmentPath = (Resolve-Path (Join-Path $repositoryRoot $EnvironmentFile)).Path
$destination = Join-Path $repositoryRoot $DestinationDirectory
New-Item -ItemType Directory -Force -Path $destination | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$containerBackup = "/app/runtime/streamml-backup-$stamp.sqlite3"
$hostBackup = Join-Path $destination "streamml-$stamp.sqlite3"
$compose = @("compose", "--env-file", $environmentPath, "-f", $composeFile)

try {
    & docker @compose exec -T -e "STREAMML_BACKUP_PATH=$containerBackup" api python -c "import os,sqlite3; source=sqlite3.connect('/app/runtime/streamml.sqlite3'); target=sqlite3.connect(os.environ['STREAMML_BACKUP_PATH']); source.backup(target); target.close(); source.close()"
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear la copia consistente dentro del contenedor." }
    & docker @compose cp "api:$containerBackup" $hostBackup
    if ($LASTEXITCODE -ne 0) { throw "No se pudo copiar el respaldo al host." }
}
finally {
    & docker @compose exec -T -e "STREAMML_BACKUP_PATH=$containerBackup" api python -c "import os,pathlib; pathlib.Path(os.environ['STREAMML_BACKUP_PATH']).unlink(missing_ok=True)" 2>$null
}

Write-Host "Respaldo consistente creado en: $hostBackup"
