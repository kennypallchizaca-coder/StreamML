# Operación, pruebas y correcciones verificadas

Este documento es la referencia corta y ejecutable para una instalación limpia.
Las instrucciones detalladas de seguridad y despliegue público están en
[`deployment.md`](deployment.md), y la guía de desarrollo local está en
[`guia-nuevos-equipos.md`](guia-nuevos-equipos.md).

## Requisitos previos

- Python 3.11 o posterior.
- Node.js 22 o posterior y npm.
- Docker Engine con el complemento `docker compose` para el entorno integrado.
- Para producción: DNS público, certificado TLS válido y los puertos TCP 80/443 y
  UDP 8189 disponibles. El conector de OBS requiere OBS WebSocket 5.x en el equipo
  de OBS; no se instala ni se expone en el servidor.

## Instalación y ejecución local

Todos los comandos se ejecutan desde la raíz `Adaptive-Streaming-ai`.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
```

La plantilla `.env.example` es exclusivamente para desarrollo: usa HTTP local,
cookies no seguras y secretos de prueba suficientemente largos para que la API
pueda arrancar. Nunca se debe desplegar ni copiar al servidor. En otra terminal:

```powershell
npm --prefix apps/frontend ci
$env:VITE_API_BASE_URL = "http://localhost:8000/api/v1"
$env:VITE_WS_BASE_URL = "ws://localhost:8000/ws"
npm --prefix apps/frontend run dev
```

Como alternativa, el entorno integrado local usa valores aislados del archivo
Compose y se abre en `http://localhost`:

```powershell
docker compose -f infrastructure/docker/docker-compose.local.yml up --build
```

## Variables de entorno de producción

Copiar `deployment/.env.example` a `deployment/.env`, protegerlo con permisos
restrictivos y reemplazar todos los `CHANGE_ME`. Se requieren, como mínimo:

- `STREAMML_TOKEN_SECRET` y `STREAMML_MEDIA_AUTH_SECRET`: valores distintos,
  aleatorios y de al menos 32 caracteres.
- `STREAMML_ALLOWED_ORIGINS` y `STREAMML_MEDIAMTX_PUBLIC_BASE`: URLs HTTPS del
  dominio público.
- `STREAMML_BOOTSTRAP_EMAIL` y `STREAMML_BOOTSTRAP_PASSWORD`: cuenta inicial;
  la contraseña debe tener al menos 12 caracteres.
- `TLS_CERT_FILE` y `TLS_KEY_FILE`: rutas absolutas legibles del certificado y
  su clave privada.
- `MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS`: nombre DNS público usado por los clientes.

No introducir credenciales en argumentos de comandos, logs, repositorios ni el
archivo `.env` de desarrollo. Los destinos RTMP(S) son opcionales y, si se usan,
se declaran solamente en `STREAMML_RESTREAM_CONFIG_JSON` dentro de
`deployment/.env`.

## Pruebas y verificaciones antes de desplegar

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python scripts\verify_release.py
.venv\Scripts\python scripts\check_no_secrets.py --history
npm --prefix apps/frontend run lint
npm --prefix apps/frontend run test
npm --prefix apps/frontend run build
docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml config --quiet
```

`ruff` forma parte de `requirements.txt`; cuando esté instalado, también ejecutar
`.venv\Scripts\python -m ruff check .`. La verificación de Compose detecta variables
faltantes y errores de interpolación, pero no sustituye una prueba de certificados,
OBS, WebRTC/ICE, red móvil o destinos RTMP reales.

## Despliegue

1. Ejecutar todas las verificaciones anteriores en el commit a publicar.
2. Copiar y completar `deployment/.env` en el servidor, sin subirlo a Git.
3. Validar y arrancar:

   ```powershell
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml config
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml up -d --build
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml ps
   ```

4. Confirmar `https://<dominio>/health` y probar una sesión autenticada, publicación,
   reproducción y el conector de OBS desde una red externa. Consultar
   [`deployment.md`](deployment.md) para respaldo, actualización y aceptación de
   medios.

El registro de modelos oficial forma parte de la imagen de API; no requiere un
directorio de modelos montado en el host. Una actualización de modelos exige
reconstruir y publicar una nueva imagen, para que los hashes verificados y el
binario desplegado sigan siendo el mismo release.

## Errores encontrados y solución aplicada

| Hallazgo | Causa raíz | Solución |
| --- | --- | --- |
| La imagen de API incluía herramientas de pruebas, lint y visualización. | El Dockerfile instalaba `requirements.txt` en vez del conjunto mínimo de runtime. | Ahora instala `requirements-api.txt`, reduciendo superficie, tamaño y tiempo de construcción en producción. |
| La API dependía de un bind mount del registro de modelos del host. | El contenedor no era autocontenido y el host podía sustituir artefactos después de construir la imagen. | El registro oficial se incorpora a la imagen de API y conserva la validación de hashes al inicio; Compose solo persiste la base de datos. |
| La plantilla `.env.example` no podía iniciar la API local. | Se marcaba como producción, exigía HTTPS/cookies seguras y sus secretos de ejemplo tenían menos de 32 caracteres. | Se convirtió en una plantilla explícita de desarrollo con orígenes HTTP locales, cookies compatibles y secretos válidos. La plantilla de producción permanece en `deployment/.env.example`. |
| Los asistentes de configuración escribían el `.env` de desarrollo y podían omitir TLS aun cuando Compose de producción lo exige. Además, mostraban la contraseña y usaban reemplazos frágiles para caracteres especiales. | La configuración de desarrollo y producción compartía una plantilla con semánticas incompatibles. | `setup.ps1` y `setup.sh` ahora generan `deployment/.env`, solicitan la contraseña sin eco, validan correo, dominio y rutas TLS existentes, y escriben valores de dotenv entre comillas escapadas. |
| La carga inicial del frontend mostraba un 401 en consola para visitantes sin cookie y el formulario decía “Sign up” al iniciar sesión. | La UI usaba un endpoint de usuario que exige autenticación para detectar una sesión inexistente y había textos inconsistentes. | Se añadió `/api/v1/auth/session`, que devuelve el estado anónimo con 200; la UI lo usa al arrancar, declara el contrato `authenticated` en TypeScript y corrige los textos/registro público cerrado. |
| El modelo predictivo podía permanecer bloqueado ante pausas operativas breves o filas de telemetría parcial. | El resampler rechazaba cualquier intervalo mayor de 2 s y trataba una fila VDO sin capacidad como un fallo total, pese a que el conector admite hasta 10 s de espera de API y el teléfono puede omitir una estimación puntual. | Ahora descarta solo las filas sin capacidad, interpola pausas acotadas de hasta 15 s en la cuadrícula requerida de 1 Hz y rechaza interrupciones mayores, manteniendo la protección contra datos ausentes materiales. |
| El monitor podía mostrar MediaMTX como “Conectado” aun cuando solo OBS reportaba salida local. | La telemetría de OBS no confirma que MediaMTX haya autenticado ni recibido el stream. | El estado se presenta como “Sin verificar” hasta que exista una comprobación directa del servidor de medios; además, la previsualización explica cuándo falta una señal publicada. |
| Edge podía descargar la señal HLS y quedarse pausado en `0:00`. | Algunas instalaciones de Chromium/Edge declaran HLS nativo, pero no avanzan correctamente con listas LL-HLS fMP4 de MediaMTX. | El frontend prioriza `hls.js` mediante Media Source Extensions y conserva HLS nativo únicamente como alternativa compatible. También reintenta el inicio automático al recibir metadatos, datos o un nuevo fragmento. |
| La primera vista previa pagaba todo el tiempo de creación del muxer HLS. | `hlsAlwaysRemux` estaba desactivado, por lo que MediaMTX comenzaba a generar HLS solo tras la solicitud del navegador. | MediaMTX inicia el muxer al recibir el publicador RTMP. OBS debe usar un intervalo de fotogramas clave de 2 s para mantener bajo el tiempo hasta el primer segmento. |
| El worker no podía verificar ni leer la señal RTMP para restaurar un destino externo. | FFmpeg recibía usuario y contraseña en el bloque `userinfo` de la URL, pero MediaMTX exige `user` y `pass` como parámetros de consulta para RTMP. | Las sondas y el restream interno construyen la URL RTMP con parámetros codificados; la API sigue validando el usuario interno, el secreto y la ruta opaca antes de autorizar la lectura. |
| La sonda de señal del worker podía dar un falso negativo después de cuatro segundos aunque MediaMTX estuviera recibiendo video. | `ffprobe` no siempre finaliza por sí solo al inspeccionar una entrada RTMP en vivo; el timeout se interpretaba como falta de señal. | La sonda consulta la API de control de MediaMTX, disponible solo en la red privada de Compose. La comprobación tarda milisegundos, no abre un lector RTMP adicional y el restream vuelve al video en vivo tras tres comprobaciones de un segundo. |
| La tarjeta de Nexa mostraba a la vez `Estable` y `Construyendo contexto`. | El estado pendiente del modelo predictivo tenía prioridad visual sobre una decisión estable ya emitida por el agente reactivo. | Una decisión operativa estable ahora conserva la pose y etiqueta `Señal estable`; el aviso independiente sigue explicando que el predictivo completa su ventana de diez minutos. |
| El predictivo permanecía esperando cuando VDO.Ninja reportaba latencia pero no una estimación de bitrate. | La fusión sustituía toda la capacidad de red por la muestra parcial del teléfono y eliminaba la medición válida del conector de OBS. | Las métricas disponibles del teléfono se superponen a la sonda del equipo OBS; si falta capacidad móvil se conserva la capacidad medida por el conector. Una desconexión o muestra obsoleta del teléfono continúa invalidando la señal para no ocultar una caída real. |
| `npm audit` informa una alerta alta en React Router 7.18.1. | La alerta afecta exclusivamente las Server Actions del modo experimental RSC; StreamML es una SPA con `BrowserRouter`, no habilita RSC ni expone esas acciones. `react-router-dom` todavía no publica una versión 8 compatible con el parche disponible en `react-router`. | Se fijó la versión estable 7.18.1, se verificó que la auditoría de dependencias de producción no tenga vulnerabilidades críticas y se evitó forzar una mezcla incompatible de versiones mayores. Actualizar ambos paquetes juntos cuando exista una versión corregida de `react-router-dom`. |
| Los límites y TTL inválidos producían un `ValueError` genérico al arrancar. | La conversión directa con `int()` no traducía el error a una configuración accionable. | La configuración ahora valida los enteros positivos durante la carga y devuelve el nombre exacto de la variable. Hay pruebas parametrizadas para texto, cero y negativos. |
| `ruff check .` fallaba aunque el código de runtime estaba limpio. | Ruff analizaba imports intermedios de notebooks de investigación, que son válidos por su ejecución por celdas y no forman parte del release. | Se excluyó `notebooks/` de Ruff; el lint cubre el código y scripts ejecutables distribuidos. |
| La documentación indicaba un comando de Compose incompleto y describía un algoritmo predictivo distinto del implementado. | Documentación desalineada con `deployment/.env` y con los artefactos/modelo. | Se documentó el uso obligatorio de `--env-file deployment/.env`, la ejecución y pruebas actuales; README indica Logistic Regression de forma consistente. |
