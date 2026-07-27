# Guía para nuevos equipos

Esta guía prepara un equipo nuevo para ejecutar StreamML localmente, contribuir
con cambios y desplegarlo de forma segura. Ejecuta todos los comandos desde la
raíz `Adaptive-Streaming-ai`.

## Requisitos

- Git.
- Docker Engine o Docker Desktop con `docker compose`.
- Para desarrollo nativo: Python 3.11 y Node.js 22 con npm.
- Para conectar OBS: OBS Studio con WebSocket 5.x activo, autenticado y limitado
  a `127.0.0.1`.

En OBS configura el intervalo de fotogramas clave en **2 segundos**. HLS necesita
un fotograma clave para iniciar cada segmento; dejar el valor automático puede
añadir varios segundos a la primera vista previa. StreamML prepara el muxer HLS
desde que recibe RTMP y el frontend inicia la reproducción en cuanto el primer
segmento es decodificable.

En Windows, abre Docker Desktop y comprueba que el motor esté activo antes de
continuar. Nunca publiques el puerto WebSocket de OBS (`4455`).

## Obtener el proyecto

```powershell
git clone https://github.com/kennypallchizaca-coder/STREAM-MACHINELEARNING.git
cd STREAM-MACHINELEARNING/Adaptive-Streaming-ai
docker compose version
```

### Alternativa: paquete de entrega

En lugar de clonar Git, el equipo responsable puede entregar
`StreamML-production-<fecha>.zip` junto con su archivo `.sha256`, generado con
`scripts/Empaquetar-StreamML.ps1`. Verifica el checksum, extrae el ZIP y entra
en la carpeta resultante. El paquete no incluye datos locales, certificados ni
secretos; cada servidor debe crear su propio `deployment/.env`.

## Entorno local integrado: recomendado

Este modo inicia API, frontend, nginx, MediaMTX y el worker de medios con
configuración aislada de desarrollo. Los modelos oficiales se incluyen en la
imagen de API y se validan al arrancar.

```powershell
docker compose -f infrastructure/docker/docker-compose.local.yml up -d --build
docker compose -f infrastructure/docker/docker-compose.local.yml ps
```

Abre [http://localhost](http://localhost) e inicia sesión con:

- Correo: `admin@localhost.com`
- Contraseña: `password123456`

Para consultar un servicio concreto sin exponer secretos:

```powershell
docker compose -f infrastructure/docker/docker-compose.local.yml logs --tail=100 api
docker compose -f infrastructure/docker/docker-compose.local.yml logs --tail=100 mediamtx
docker compose -f infrastructure/docker/docker-compose.local.yml ps
```

Para detenerlo, conserva los datos; no uses `--volumes` salvo que quieras
eliminar intencionalmente la base de datos local:

```powershell
docker compose -f infrastructure/docker/docker-compose.local.yml down
```

## Desarrollo nativo de API y frontend

Usa este modo para editar código con recarga rápida. El flujo completo de
medios autenticados se prueba con el entorno Docker integrado; no intentes
iniciar MediaMTX por separado con la API nativa, porque su autorización vive
en la red privada de Compose.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
```

En otra terminal:

```powershell
npm --prefix apps/frontend ci
$env:VITE_API_BASE_URL = "http://localhost:8000/api/v1"
$env:VITE_WS_BASE_URL = "ws://localhost:8000/ws"
npm --prefix apps/frontend run dev
```

El frontend nativo se abre normalmente en `http://localhost:5173`. La plantilla
`.env.example` es solo para desarrollo; no contiene valores de producción.

## Pruebas antes de enviar cambios

```powershell
python -m pytest -q
python scripts/verify_release.py
python scripts/check_no_secrets.py --history
python -m ruff check .
npm --prefix apps/frontend run lint
npm --prefix apps/frontend run test
npm --prefix apps/frontend run build
```

`verify_release.py` comprueba hashes, contratos y versiones de los modelos.
El modelo reactivo opera con las mediciones actuales. El predictivo requiere
una ventana de unos diez minutos de capacidad de red; tolera pausas cortas de
telemetría, pero rechaza cortes relevantes para no inventar una predicción.

## Producción

La producción requiere DNS público, certificado TLS válido, puertos TCP 80/443
y UDP 8189 disponibles. El conector de OBS permanece en el equipo de OBS, no
en el servidor Docker.

1. Ejecuta `setup.ps1` en Windows o `bash setup.sh` en Linux/macOS. El asistente
   genera `deployment/.env`, solicita rutas TLS y secretos seguros.
2. Revisa que ningún valor `CHANGE_ME` permanezca en `deployment/.env` y no lo
   subas a Git.
3. Valida y arranca:

   ```powershell
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml config --quiet
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml up -d --build
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml ps
   ```

4. Comprueba `https://<tu-dominio>/health`, el inicio de sesión, una publicación
   de prueba y la reproducción HLS/WebRTC desde una red externa.

La guía operativa completa, respaldo y aceptación de medios está en
[deployment.md](deployment.md). Para la lista de variables, verificaciones y
errores corregidos consulta [operacion-y-verificacion.md](operacion-y-verificacion.md).

## Problemas frecuentes

| Síntoma | Acción segura |
| --- | --- |
| Un puerto está ocupado | Identifica el proceso con `netstat -ano | findstr :<puerto>` en Windows o `lsof -i :<puerto>` en Linux/macOS. Detén solo el proceso identificado. |
| Un contenedor no está saludable | Ejecuta `docker compose -f infrastructure/docker/docker-compose.local.yml ps` y consulta los logs del servicio concreto. |
| El predictivo dice “Esperando datos” | Mantén telemetría de capacidad durante diez minutos. Revisa que el teléfono y el conector sigan conectados. |
| No hay vista previa | Confirma que OBS usa el servidor y clave RTMP de la sesión y que el intervalo de fotogramas clave sea 2 s. Si WebRTC no admite el codec, el reproductor usa HLS y se reconecta automáticamente. |
| La API nativa no inicia | Activa `.venv`, instala `requirements.txt` y usa la plantilla `.env.example` sin modificar sus controles de desarrollo. |

No ejecutes comandos globales que detengan o eliminen todos los contenedores del
equipo. Preserva `deployment/.env`, certificados, volúmenes y respaldos fuera
del control de versiones.
