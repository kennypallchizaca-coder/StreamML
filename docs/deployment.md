# Despliegue en línea de StreamML

Este repositorio contiene una implementación de nodo único lista para producción.
Una instalación pública específica solo se acepta después de que su OBS real,
teléfono, red, MediaMTX, WebRTC, credenciales de plataforma y certificado TLS
de confianza pasen la verificación de puesta en marcha descrita abajo.

## Requisitos previos

- Docker Engine con Compose
- Un nombre DNS público y certificado TLS de confianza para uso en línea
- Puerto UDP 8189 accesible por clientes WebRTC, o un servicio TURN configurado
- OBS WebSocket 5.x habilitado solo en localhost con autenticación
- Artefactos oficiales del release de StreamML ya presentes en `models/registry/`

## Verificación de puesta en marcha para producción

No usar `deployment/.env.example` como configuración de ejecución. Antes de un
despliegue público, todo lo siguiente debe cumplirse:

- El commit objetivo tiene una ejecución exitosa de CI y `python scripts/verify_release.py`
  reporta `STREAMML RELEASE VERIFIED`.
- `python scripts/check_no_secrets.py --history` pasa antes del primer push.
- `deployment/.env` es un archivo no rastreado con valores únicos y aleatorios para
  ambos valores `STREAMML_*_SECRET` y la contraseña bootstrap. Almacenar sus valores
  en un gestor de secretos o contraseñas, no en un chat, perfil de shell o commit.
- El certificado TLS cubre el nombre DNS configurado; los puertos TCP 80/443 y UDP
  8189 son accesibles según sea necesario. No publicar el puerto 4455 de OBS, la API
  de MediaMTX, ni los puertos HLS o WHEP directamente.
- La computadora con OBS tiene las escenas `StreamML Live` y `StreamML Backup` (o los
  equivalentes configurados), WebSocket de OBS autenticado solo en loopback, y un
  modo de salida H.264/AAC probado.
- Los destinos RTMP(S), si los hay, han sido probados con claves que no son de producción
  antes de colocar sus claves reales en el archivo de entorno ignorado del despliegue.

En un servidor Linux, crear el archivo de despliegue con permisos restrictivos
antes de editarlo:

```sh
install -m 600 /dev/null deployment/.env
```

Generar secretos con un gestor de secretos aprobado. Si no hay uno disponible,
Python puede generar un valor URL-safe localmente; copiarlo directamente al archivo
de entorno protegido y no conservarlo en el historial del shell.

El despliegue con Compose monta `models/registry/` como solo lectura. Los datos
versionados y los contratos de features residen en `src/streamml/config/` y se
copian con el código fuente de la API. El despliegue no entrena, sobrescribe ni
regenera artefactos de modelo.

## Despliegue en servidor

1. Copiar `deployment/.env.example` a `deployment/.env` fuera del control de versiones.
2. Reemplazar cada `CHANGE_ME` y ambas rutas TLS.
   `STREAMML_MEDIA_AUTH_SECRET` debe ser al menos 32 caracteres aleatorios URL-safe;
   MediaMTX lo usa como autenticación Basic en la URL de callback aislada.
3. Validar la configuración sin iniciar servicios:

   ```powershell
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml config
   ```

4. Construir e iniciar:

   ```powershell
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml up -d --build
   ```

5. Inspeccionar el estado de salud sin imprimir valores de entorno:

   ```powershell
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml ps
   ```

6. Confirmar la API desde dentro de la red privada de Docker:

   ```powershell
   docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml exec api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3).read().decode())"
   ```

El punto de entrada público es nginx en HTTPS/WSS. La base de datos de la API usa un
volumen persistente de Docker, mientras que la API de control y los listeners de métricas
de MediaMTX no tienen puerto de host. Los listeners RTMP, HLS directo y WHEP directo
están vinculados al loopback del host por defecto (`1935`, `8888` y `8889`) para
diagnósticos locales; no cambiarlos a interfaces públicas. MediaMTX también se une a la
red edge para que Docker materialice esos bindings explícitos, mientras que la API
permanece aislada en la red backend. La API devuelve una base compartida
`https://<host>/media/`: los recursos WHEP/WHIP enrutan a WebRTC y las listas de
reproducción o segmentos enrutan a HLS.

El asistente de despliegue valida el certificado TLS y la clave privada como un par PEM
coincidente antes de que se permita iniciar Compose, previniendo bucles de reinicio de
nginx causados por archivos placeholder o no coincidentes.

Las rutas de medios son identificadores opacos devueltos por la API de sesión autenticada:

```text
stream-<32 caracteres hexadecimales en minúscula>
```

MediaMTX delega cada decisión de publicación/lectura a la API a través de una red Docker
aislada. El callback no es enrutado por nginx y cada solicitud pública de medios aún
necesita un token de corta duración, con alcance de sesión; una ruta sola nunca es
autorización.

## Operaciones, respaldo y actualizaciones

Los contenedores usan políticas de reinicio, sistemas de archivos de solo lectura cuando
es posible, sistemas de archivos temporales limitados, `no-new-privileges` y el driver
de log `local` de Docker con rotación de 10 MiB × 5 por servicio. Monitorear
`docker compose ps` y el estado de salud del contenedor; preservar logs fuera de Docker
si se requiere retención más prolongada que ese límite.

La base de datos SQLite de la API es un almacén de despliegue de nodo único. Respaldarla
antes de una actualización y probar la restauración en un host que no sea de producción.
El script usa la API de respaldo en línea de SQLite, por lo que el resultado incluye
datos WAL commitados de forma consistente:

```powershell
./scripts/Backup-StreamML.ps1
```

Almacenar el archivo resultante cifrado y fuera del servidor. Para verificar una
restauración, copiarlo a una instalación que no sea de producción, iniciar la API y
requerir que `/health/ready` reporte la versión de esquema esperada y una base de datos
sana. No sobrescribir una base de datos de producción en ejecución.

Para una actualización: respaldar la base de datos, revisar cambios de imagen y
dependencias, ejecutar las verificaciones de release y secretos, luego usar
`up -d --build`. Nunca ejecutar `down --volumes` en producción a menos que la eliminación
de la base de datos sea intencional y exista un respaldo verificado. Fijar
`MEDIAMTX_IMAGE` a `1.19.2` es deliberado; actualizarlo solo después de reproducir las
pruebas de humo de medios descritas abajo.

## Conector local de StreamML

El conector se ejecuta en la misma computadora que OBS; no ponerlo en Compose y no
abrir el puerto 4455 de OBS en un router o firewall público.

```powershell
py -3.11 -m venv .venv-connector
.venv-connector\Scripts\python -m pip install -e apps/connector
$env:STREAMML_API_URL = "https://streamml.example.com"
$env:OBS_WEBSOCKET_HOST = "127.0.0.1"
$env:OBS_WEBSOCKET_PORT = "4455"
.venv-connector\Scripts\streamml-connector --pair
```

`--pair` lee el código temporal sin eco en la terminal. La contraseña de OBS se lee
desde `OBS_WEBSOCKET_PASSWORD` cuando está configurada explícitamente, de lo contrario
mediante un prompt sin eco. El token de la API se almacena solo en el keyring del
sistema operativo; no hay un respaldo en texto plano.

Después del primer enlace exitoso, ejecutar sin `--pair`:

```powershell
.venv-connector\Scripts\streamml-connector
```

El conector invoca `GetStats` y `GetStreamStatus` de OBS para telemetría. También acepta
solo tres operaciones de control autenticadas: actualizar el perfil de StreamML, seleccionar
`StreamML Backup` y restaurar `StreamML Live`. Nunca expone un endpoint RPC genérico de OBS
y nunca inicia ni detiene una transmisión. Crear ambas escenas antes de iniciar el conector,
o sobreescribir `STREAMML_LIVE_SCENE` y `STREAMML_BACKUP_SCENE`.

El conector mide subida, descarga, latencia, jitter y sondas fallidas contra la ruta
autenticada de la API cada cinco segundos. `output_bitrate_kbps` sigue siendo un derivado
del contador de bytes de OBS y nunca se reetiqueta como capacidad de subida. Configurar
el intervalo de sondeo y el payload limitado con `STREAMML_NETWORK_PROBE_INTERVAL_SECONDS`
y `STREAMML_NETWORK_PROBE_BYTES`.

## Publicación de medios

Preferir WHIP autenticado a través de la ruta HTTPS `/media/` cuando la versión instalada
de OBS y los codecs hayan sido verificados. RTMP sigue disponible como respaldo local en
`rtmp://127.0.0.1:1935/<ruta-media>`.

MediaMTX no transcodifica la entrada en vivo. Confirmar H.264 de video y AAC de audio en
OBS para que sean compatibles con el archivo de respaldo generado y los reproductores
objetivo. El `media-worker` ejecuta un proceso FFmpeg supervisado para cada destino RTMP(S)
nombrado declarado en `STREAMML_RESTREAM_CONFIG_JSON`. Sondea la ruta en vivo de MediaMTX,
envía `/fallback/fallback.mp4` mientras no esté disponible, y restaura la entrada en vivo
después de tres sondas exitosas. El cambio de escena de OBS proporciona respaldo por
separado para la ruta interna de MediaMTX/navegador.

Ejemplo sin imprimir claves reales en los logs:

```text
STREAMML_RESTREAM_CONFIG_JSON={"stream-<id>":{"youtube":"rtmps://host/app/SECRETO"}}
```

Reiniciar `media-worker` después de cambiar destinos. Validar WHEP/WebRTC, HLS, la
transición de respaldo y cada plataforma externa por separado.

## Detener servicios

```powershell
docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml down
```

No agregar `--volumes` a menos que la eliminación intencional de la base de datos de
sesiones de la API haya sido aprobada por separado y respaldada.

## Pruebas que aún requieren servicios reales

- Autenticación de OBS WebSocket y exposición solo en localhost
- Recuperación del conector después de reinicio de OBS y pérdida de Internet
- Telemetría HTTPS y WebSocket de sesión autenticado
- Publicación de OBS a MediaMTX a través de WHIP y RTMP
- WHEP/WebRTC a través de una red externa, ICE/TURN y respaldo HLS
- Teléfono a VDO.Ninja a OBS, incluyendo eventos `postMessage` con origen verificado
- Validación externa de la sonda HTTP contra una herramienta de red calibrada
- Cambios de perfil en vivo con el modo de salida y codificador OBS seleccionado
- Respaldo automático y recuperación con parámetros de codec H.264/AAC coincidentes
- Retransmisión FFmpeg a cada plataforma RTMP(S) configurada
- Renovación de certificados, aislamiento multi-usuario y comportamiento bajo carga sostenida

Tratar esta lista como la verificación final de aceptación para producción. Una suite
verde de pruebas unitarias/integración demuestra el repositorio y los servicios aislados;
no puede demostrar condiciones de radio móvil, ingesta RTMP de terceros o el comportamiento
real del codificador.
