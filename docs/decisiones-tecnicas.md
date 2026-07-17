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

El enlace `push` de VDO.Ninja pertenece al teléfono; el enlace `view` se utiliza como fuente de visualización. OBS envía el programa por RTMP/WHIP a MediaMTX y FFmpeg mantiene la retransmisión o el respaldo.

El registro oficial comprueba hashes, versiones de librerías, contratos y clases antes de crear la aplicación. El estado `production_ready` significa que los artefactos fueron verificados y los controles operativos están activos; no significa que 17 sesiones públicas demuestren generalización universal. La prueba física con el teléfono, operador móvil y destino real sigue siendo un criterio de aceptación del despliegue.

## Control autónomo

Las acciones de ML no llegan directamente a OBS. El agente determinista aplica margen de seguridad, histéresis, cambios de un solo nivel, tiempo mínimo entre cambios y recuperación estable. El conector solo acepta comandos autenticados y de tipos permitidos: perfil, escena de respaldo y restauración del vivo.

## Observabilidad y cierre

La API emite JSON estructurado con identificador de solicitud, latencia y valores sensibles redactados. nginx excluye parámetros de consulta de sus registros. Uvicorn, los workers y los contenedores tienen periodos de cierre; el hub WebSocket libera sus suscriptores al finalizar.
