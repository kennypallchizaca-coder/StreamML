<#
.SYNOPSIS
Asistente de configuración de StreamML para producción.
#>

$ErrorActionPreference = 'Stop'

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   Asistente de Configuración StreamML   " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

$envFile = ".env"
$envTemplate = ".env.example"

if (-not (Test-Path $envTemplate)) {
    Write-Error "El archivo $envTemplate no existe. Asegúrate de estar en el directorio raíz del proyecto."
    exit 1
}

$envContent = Get-Content $envTemplate -Raw

function New-Secret {
    return [Guid]::NewGuid().ToString().Replace('-', '') + [Guid]::NewGuid().ToString().Replace('-', '')
}

Write-Host "Configuración del Dominio" -ForegroundColor Yellow
$domain = Read-Host "Ingresa tu dominio principal (ej. stream.mi-empresa.com) [Dejar vacío para usar localhost]"
if ([string]::IsNullOrWhiteSpace($domain)) {
    $domain = "localhost"
    $protocol = "http"
} else {
    $protocol = "https"
}

Write-Host "`nConfiguración de Administrador" -ForegroundColor Yellow
$email = Read-Host "Correo del administrador inicial"
$password = Read-Host "Contraseña temporal del administrador"

Write-Host "`nConfiguración de Certificados SSL (Opcional si usas localhost)" -ForegroundColor Yellow
if ($domain -ne "localhost") {
    $tlsCert = Read-Host "Ruta al certificado SSL (ej. ./certs/fullchain.pem) [Presiona Enter para ignorar por ahora]"
    $tlsKey = Read-Host "Ruta a la llave SSL (ej. ./certs/privkey.pem) [Presiona Enter para ignorar por ahora]"
} else {
    $tlsCert = ""
    $tlsKey = ""
}

$tokenSecret = New-Secret
$mediaAuthSecret = New-Secret

$envContent = $envContent -replace "(?m)^STREAMML_ENVIRONMENT=.*", "STREAMML_ENVIRONMENT=production"
$envContent = $envContent -replace "(?m)^STREAMML_TOKEN_SECRET=.*", "STREAMML_TOKEN_SECRET=$tokenSecret"
$envContent = $envContent -replace "(?m)^STREAMML_MEDIA_AUTH_SECRET=.*", "STREAMML_MEDIA_AUTH_SECRET=$mediaAuthSecret"
$envContent = $envContent -replace "(?m)^STREAMML_ALLOWED_ORIGINS=.*", "STREAMML_ALLOWED_ORIGINS=$protocol`://$domain"
$envContent = $envContent -replace "(?m)^STREAMML_MEDIAMTX_PUBLIC_BASE=.*", "STREAMML_MEDIAMTX_PUBLIC_BASE=$protocol`://$domain/media"
$envContent = $envContent -replace "(?m)^STREAMML_BOOTSTRAP_EMAIL=.*", "STREAMML_BOOTSTRAP_EMAIL=$email"
$envContent = $envContent -replace "(?m)^STREAMML_BOOTSTRAP_PASSWORD=.*", "STREAMML_BOOTSTRAP_PASSWORD=$password"

if ([string]::IsNullOrWhiteSpace($tlsCert) -or [string]::IsNullOrWhiteSpace($tlsKey)) {
    $envContent = $envContent -replace "(?m)^TLS_CERT_FILE=.*\r?\n?", ""
    $envContent = $envContent -replace "(?m)^TLS_KEY_FILE=.*\r?\n?", ""
} else {
    $envContent += "`nTLS_CERT_FILE=$tlsCert`nTLS_KEY_FILE=$tlsKey"
}

Set-Content -Path $envFile -Value $envContent -Encoding UTF8
Write-Host "`n¡Configuración completada! Se ha generado tu archivo .env con secretos seguros." -ForegroundColor Green
Write-Host "Ahora puedes iniciar el sistema con: docker-compose -f infrastructure/docker/docker-compose.yml up -d" -ForegroundColor Cyan
