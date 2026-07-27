<#
.SYNOPSIS
Asistente de configuración de StreamML para producción.
#>

$ErrorActionPreference = 'Stop'

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   Asistente de Configuración StreamML   " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

$envFile = "deployment/.env"
$envTemplate = "deployment/.env.example"

if (-not (Test-Path $envTemplate)) {
    Write-Error "El archivo $envTemplate no existe. Asegúrate de estar en el directorio raíz del proyecto."
    exit 1
}

$envContent = Get-Content $envTemplate -Raw

function New-Secret {
    return [Guid]::NewGuid().ToString().Replace('-', '') + [Guid]::NewGuid().ToString().Replace('-', '')
}

Write-Host "Configuración del Dominio" -ForegroundColor Yellow
$domain = Read-Host "Ingresa tu dominio público (ej. stream.mi-empresa.com)"
if ([string]::IsNullOrWhiteSpace($domain) -or $domain -match '[\s/:]') {
    throw "Se requiere un nombre DNS público válido. Para desarrollo local usa docker-compose.local.yml."
}
$protocol = "https"

Write-Host "`nConfiguración de Administrador" -ForegroundColor Yellow
$email = Read-Host "Correo del administrador inicial"
$securePassword = Read-Host "Contraseña temporal del administrador" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
}
if ([string]::IsNullOrWhiteSpace($email) -or $email -notmatch '^[^\s@]+@[^\s@]+\.[^\s@]+$') {
    throw "Ingresa un correo electrónico de administrador válido."
}
if ($password.Length -lt 12 -or $password -match '[\r\n]') {
    throw "La contraseña debe tener al menos 12 caracteres y no contener saltos de línea."
}

Write-Host "`nConfiguración de Certificados SSL" -ForegroundColor Yellow
$tlsCert = Read-Host "Ruta absoluta al certificado SSL (fullchain.pem)"
$tlsKey = Read-Host "Ruta absoluta a la llave SSL (privkey.pem)"
if (-not [IO.Path]::IsPathFullyQualified($tlsCert) -or -not (Test-Path -LiteralPath $tlsCert -PathType Leaf)) {
    throw "TLS_CERT_FILE debe ser una ruta absoluta a un certificado existente."
}
if (-not [IO.Path]::IsPathFullyQualified($tlsKey) -or -not (Test-Path -LiteralPath $tlsKey -PathType Leaf)) {
    throw "TLS_KEY_FILE debe ser una ruta absoluta a una clave privada existente."
}

$tokenSecret = New-Secret
$mediaAuthSecret = New-Secret

function Set-EnvironmentValue([string]$content, [string]$name, [string]$value) {
    $escaped = $value.Replace('\', '\\').Replace('"', '\"')
    $replacement = "$name=`"$escaped`""
    $pattern = "(?m)^" + [regex]::Escape($name) + "=.*$"
    return [regex]::Replace($content, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($match) $replacement })
}

$envContent = Set-EnvironmentValue $envContent "STREAMML_ENVIRONMENT" "production"
$envContent = Set-EnvironmentValue $envContent "STREAMML_TOKEN_SECRET" $tokenSecret
$envContent = Set-EnvironmentValue $envContent "STREAMML_MEDIA_AUTH_SECRET" $mediaAuthSecret
$envContent = Set-EnvironmentValue $envContent "STREAMML_ALLOWED_ORIGINS" "$protocol`://$domain"
$envContent = Set-EnvironmentValue $envContent "STREAMML_MEDIAMTX_PUBLIC_BASE" "$protocol`://$domain/media"
$envContent = Set-EnvironmentValue $envContent "MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS" $domain
$envContent = Set-EnvironmentValue $envContent "STREAMML_BOOTSTRAP_EMAIL" $email
$envContent = Set-EnvironmentValue $envContent "STREAMML_BOOTSTRAP_PASSWORD" $password
$envContent = Set-EnvironmentValue $envContent "TLS_CERT_FILE" $tlsCert
$envContent = Set-EnvironmentValue $envContent "TLS_KEY_FILE" $tlsKey

Set-Content -Path $envFile -Value $envContent -Encoding UTF8
Write-Host "`n¡Configuración completada! Se ha generado $envFile con secretos seguros." -ForegroundColor Green
Write-Host "Ahora puedes iniciar el sistema con: docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml up -d --build" -ForegroundColor Cyan
