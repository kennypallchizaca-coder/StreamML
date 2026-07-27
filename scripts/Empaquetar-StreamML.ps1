<#
.SYNOPSIS
Genera un ZIP reproducible de StreamML apto para entregar o desplegar.

.DESCRIPTION
Empaqueta el árbol de trabajo actual sin bases de datos locales, secretos,
certificados, entornos virtuales, dependencias instaladas ni registros. Antes
de generar el artefacto ejecuta los verificadores de secretos y de modelos,
salvo que se indique -SkipVerification.
#>

[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\dist"),
    [switch]$SkipVerification
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git es necesario para seleccionar los archivos publicables del paquete.'
}

if (-not $SkipVerification) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw 'No se encontró Python. Usa -SkipVerification solo si ya validaste el release en CI.'
    }
    Push-Location $repositoryRoot
    try {
        & $python.Source scripts/check_no_secrets.py
        if ($LASTEXITCODE -ne 0) { throw 'La verificación de secretos falló.' }
        & $python.Source scripts/verify_release.py
        if ($LASTEXITCODE -ne 0) { throw 'La verificación de modelos falló.' }
    } finally {
        Pop-Location
    }
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$packageName = "StreamML-production-$timestamp"
$resolvedOutput = [IO.Path]::GetFullPath($OutputDirectory)
$stagingDirectory = Join-Path $resolvedOutput $packageName
$archivePath = Join-Path $resolvedOutput "$packageName.zip"
$checksumPath = "$archivePath.sha256"

New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null
if (Test-Path -LiteralPath $stagingDirectory) {
    throw "La carpeta temporal del paquete ya existe: $stagingDirectory"
}

$excluded = @(
    '^data/streamml\.db$',
    '(^|/)\.env(?:\.|$)',
    '(^|/)(?:\.venv[^/]*|venv|node_modules|dist|logs|runtime)(?:/|$)',
    '\.(?:sqlite3|sqlite|db|pem|key|log)$'
)

try {
    New-Item -ItemType Directory -Path $stagingDirectory | Out-Null
    $files = @(& git -C $repositoryRoot ls-files --cached --others --exclude-standard)
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo obtener la lista de archivos publicables con Git.' }
    # This template is deliberately ignored by the broad .env rule on older
    # clones. It is safe to distribute and required for a new production host.
    $files = @($files + 'deployment/.env.example' | Select-Object -Unique)

    $copied = 0
    foreach ($relativePath in $files) {
        if (-not $relativePath) { continue }
        $normalized = $relativePath.Replace('\', '/')
        if ($normalized -ne 'deployment/.env.example' -and ($excluded | Where-Object { $normalized -match $_ })) {
            continue
        }
        $source = Join-Path $repositoryRoot $relativePath
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }
        $destination = Join-Path $stagingDirectory $relativePath
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
        $copied += 1
    }

    foreach ($required in @('README.md', 'deployment/.env.example', 'infrastructure/docker/docker-compose.yml', 'models/registry/release_manifest.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $stagingDirectory $required) -PathType Leaf)) {
            throw "El paquete no contiene el archivo obligatorio: $required"
        }
    }
    if ($copied -lt 20) { throw 'El paquete contiene muy pocos archivos; se cancela por seguridad.' }

    Compress-Archive -Path $stagingDirectory -DestinationPath $archivePath -CompressionLevel Optimal -Force
    $hash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText($checksumPath, "$hash *$([IO.Path]::GetFileName($archivePath))`n", [Text.UTF8Encoding]::new($false))
    Write-Host "Paquete creado: $archivePath" -ForegroundColor Green
    Write-Host "SHA-256: $hash" -ForegroundColor Green
    Write-Host "Archivos incluidos: $copied (sin secretos ni datos locales)." -ForegroundColor Cyan
} finally {
    if (Test-Path -LiteralPath $stagingDirectory) {
        Remove-Item -LiteralPath $stagingDirectory -Recurse -Force
    }
}
