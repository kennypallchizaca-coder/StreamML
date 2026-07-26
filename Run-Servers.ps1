param (
    [switch]$SkipDocker = $false
)

$ErrorActionPreference = "Stop"

Write-Host "Iniciando todos los servidores de StreamML..." -ForegroundColor Cyan

# 1. Start Docker containers (MediaMTX / Nginx)
if (-not $SkipDocker) {
    Write-Host "`n[1/3] Iniciando contenedores (MediaMTX y Nginx)..." -ForegroundColor Yellow
    Push-Location infrastructure/docker
    try {
        docker-compose -f docker-compose.local.yml up -d --build
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error al iniciar Docker Compose. Verifica si Docker está en ejecución." -ForegroundColor Red
        } else {
            Write-Host "Contenedores iniciados correctamente." -ForegroundColor Green
        }
    } catch {
        Write-Host "No se encontró el comando docker-compose o hubo un error." -ForegroundColor Red
    }
    Pop-Location
} else {
    Write-Host "`n[1/3] Omitiendo el inicio de contenedores Docker (--SkipDocker)." -ForegroundColor Yellow
}

# 2. Start FastAPI Backend
Write-Host "`n[2/3] Iniciando servidor API de FastAPI..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload --env-file .env"
Write-Host "API iniciada en segundo plano." -ForegroundColor Green

# 3. Start React Frontend
Write-Host "`n[3/3] Iniciando servidor Frontend (React/Vite)..." -ForegroundColor Yellow
Push-Location apps/frontend
try {
    Start-Process -NoNewWindow -FilePath "cmd.exe" -ArgumentList "/c npm run dev"
    Write-Host "Frontend iniciado. Revisa la URL en la terminal (usualmente http://localhost:5173)." -ForegroundColor Green
} catch {
  Write-Host "Error al iniciar el frontend. Asegúrate de haber ejecutado 'npm install' en 'apps/frontend'." -ForegroundColor Red
}
Pop-Location

# 4. Start OBS Connector
Write-Host "`n[4/4] Iniciando Asistente Local (Conector OBS)..." -ForegroundColor Yellow
try {
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c .\scripts\Abrir-Configuracion-StreamML.cmd"
    Write-Host "Asistente Local iniciado en segundo plano (Puerto 8765)." -ForegroundColor Green
} catch {
    Write-Host "No se pudo iniciar el Asistente Local." -ForegroundColor Red
}

Write-Host "`n¡Todos los servicios han sido lanzados!" -ForegroundColor Cyan
Write-Host "Nota: Los logs de la API se escribirán en la carpeta logs/streamml.log" -ForegroundColor Gray

