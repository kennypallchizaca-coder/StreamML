# Decisiones técnicas de StreamML

## Límites de seguridad

- La aplicación web y la API nunca reciben la contraseña de OBS. El asistente local, limitado a `127.0.0.1`, la guarda en el almacén de credenciales del sistema operativo.
- Los códigos de vínculo se almacenan como HMAC, los tokens como SHA-256 y las contraseñas de usuarios con `scrypt`. Los secretos de despliegue se inyectan únicamente al proceso de Docker mediante un archivo temporal que se sobrescribe y elimina.
- La API acepta también la convención `VARIABLE_FILE` para secretos montados por Docker/Kubernetes. Los ejemplos del repositorio contienen marcadores, no credenciales utilizables.
- OBS WebSocket solo admite loopback. Publicarlo en la LAN ampliaría innecesariamente la superficie de control del codificador.

## Persistencia y migraciones

SQLite se mantiene para una instalación de un solo nodo: simplifica las copias consistentes y evita otro servicio con credenciales. El esquema tiene migraciones versionadas y un control `PRAGMA quick_check`; `/health/ready` no declara preparado un nodo con base dañada o esquema incompleto. Para múltiples réplicas de API se deberá migrar a PostgreSQL antes de habilitarlas.

## Separación de entornos

- `development`: HTTP y cookies no seguras se permiten únicamente en loopback.
- `test`: configuración efímera utilizada por `pytest` y por pruebas de integración.
- `production`: la API rechaza el arranque si HTTPS, cookies seguras, orígenes HTTPS explícitos o URL HTTPS de medios no están activos.

Docker Compose fija `production` y ejecuta API, frontend, MediaMTX, FFmpeg y nginx con sistemas de archivos de solo lectura, usuarios sin privilegios cuando corresponde, límites de logs, reinicio automático y comprobaciones de salud.

## Streaming y Machine Learning

El enlace `push` de VDO.Ninja pertenece al teléfono y el enlace `view` se carga dentro de una fuente puente de StreamML. El conector recibe la URL puente mediante su credencial de sesión y configura automáticamente la única Browser Source de la escena Live; si la escena es ambigua no modifica nada. El puente permanece abierto en OBS, valida el origen de cada `postMessage` y solicita una única muestra `getFreshStats` cada dos segundos. Evitar consultas continuas, frescas y remotas simultáneas impide que contadores independientes produzcan ceros y picos falsos. El puente normaliza exclusivamente métricas WebRTC permitidas y las envía con un token HMAC limitado a la sesión; el objeto bruto de VDO.Ninja no sale del navegador. OBS envía el programa por RTMP/WHIP a MediaMTX y FFmpeg mantiene la retransmisión o el respaldo.

La orquestación prioriza la capacidad observada, RTT, jitter y pérdida del teléfono; conserva de la sonda del computador únicamente campos no disponibles, como la prueba de descarga. Una muestra móvil antigua queda marcada `stale`, no se presenta como medición actual y activa el mismo temporizador de respaldo que una desconexión explícita. Después de que existe un reportero móvil, StreamML nunca reemplaza una señal vencida con la conexión de la computadora: bloquea la inferencia hasta recuperar datos WebRTC frescos. Las métricas físicas de la antena celular no forman parte de WebRTC y no se simulan.

El registro oficial comprueba hashes, versiones de librerías, contratos y clases antes de crear la aplicación. El estado `production_ready` significa que los artefactos fueron verificados y los controles operativos están activos; no significa que 17 sesiones públicas demuestren generalización universal. La prueba física con el teléfono, operador móvil y destino real sigue siendo un criterio de aceptación del despliegue.

## Control autónomo

Las acciones de ML no llegan directamente a OBS. El agente determinista aplica margen de seguridad, histéresis, cambios de un solo nivel, tiempo mínimo entre cambios y recuperación estable. El conector solo acepta comandos autenticados y de tipos permitidos: perfil, escena de respaldo y restauración del vivo. Un comando que no se entrega en cinco minutos caduca para impedir que una sesión antigua cambie OBS al reconectarse mucho después.

Cada decisión conserva un `reason_code` estable y un estado operacional (`stable`, `observing`, `protecting`, `degraded`, `backup` o `recovering`). Esto permite distinguir la recomendación de cada modelo de la política final aplicada y auditar por qué se mantuvo, redujo, aumentó o cambió de escena. Las inferencias exponen únicamente resúmenes de sus entradas validadas como evidencia observada; no se presentan como explicaciones causales.

El modelo predictivo exige 600 puntos a 1 Hz. La cadencia real incluye el tiempo de las solicitudes y puede quedar ligeramente por encima de un segundo; la orquestación toma una ventana continua de mediciones reales, rechaza huecos mayores de dos segundos y aplica interpolación lineal únicamente dentro del intervalo observado para normalizarla a la cuadrícula del contrato. No extrapola valores fuera de datos medidos.

Un error de autorización de la API se trata de forma distinta a una caída de OBS: el conector se detiene con un mensaje de revinculación y no abre conexiones WebSocket repetidas. Los fallos transitorios de API conservan la conexión local con OBS y aplican reintento con backoff.

## Observabilidad y cierre

La API emite JSON estructurado con identificador de solicitud, latencia y valores sensibles redactados. nginx excluye parámetros de consulta de sus registros. Uvicorn, los workers y los contenedores tienen periodos de cierre; el hub WebSocket libera sus suscriptores al finalizar.

## Evidencia ML y criterio de aceptación

`scripts/audit_ml_data.py` detecta valores faltantes, variables constantes, desbalance, duplicados, solapamiento de ventanas y repetición de vectores entre splits. `scripts/evaluate_control_replay.py` compara un perfil fijo, control solo reactivo y el agente completo mediante un proxy QoE orientado primero a continuidad. Ambos informes se versionan en `reports/` y CI falla si están desactualizados.

El replay determinista incluido prueba regresiones de la política, pero no demuestra QoE real. La aceptación física exige sesiones nuevas e independientes, con teléfono, VDO.Ninja, OBS, red degradada y destino real; esas capturas deben evaluarse después con el mismo formato de replay.

Los cuatro notebooks reflejan la misma separación de responsabilidades. `01` audita y prepara datos, `02` reproduce la publicación oficial, `03` demuestra inferencia y control, y `04` entrena candidatos en un espacio temporal antes de integrarlos con el agente. El último notebook no presenta al agente como un modelo entrenado: documenta que los clasificadores aprenden de datos y que la política operacional es código determinista, versionado y probado.
