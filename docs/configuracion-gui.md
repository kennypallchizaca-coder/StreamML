# Configuración gráfica de StreamML

## Abrir el asistente

En Windows, abre con doble clic [Abrir-Configuracion-StreamML.cmd](../scripts/Abrir-Configuracion-StreamML.cmd). El iniciador crea un entorno aislado, instala o repara el conector solo cuando hace falta y abre `http://127.0.0.1:8765/` en el navegador. Si el asistente ya está activo, lo conserva sin reinstalar archivos en uso. No es necesario copiar comandos a una terminal.

La primera parte del asistente se usa **en la misma computadora que OBS**. La segunda parte es para el equipo que alojará Docker y el servidor de producción. Si el servidor ya está funcionando, solo configura la primera parte con la URL de su API.

También se puede llegar al asistente desde la aplicación: **Configuración → Conexiones → Abrir asistente local**. Si el servicio local no estaba abierto, ejecuta primero el archivo `.cmd`.

Al abrirlo desde el panel, el asistente adopta automáticamente el tema claro u oscuro guardado por el usuario. El botón **Tema** de la barra superior permite cambiarlo solo para el asistente cuando se abre directamente.

El centro de control y el asistente local comparten la misma fuente de verdad visual en `apps/frontend/src/theme.css`. Allí se definen colores semánticos, superficies, estados, bordes, sombras y los modos claro/oscuro; `apps/connector/streamml_connector/setup.css` solo describe la distribución del asistente usando esas variables. No agregues colores directos dentro de componentes.

## Configurar OBS y el conector

1. En OBS, activa **WebSocket Server** y conserva el host `127.0.0.1`; crea las escenas `StreamML Live` y `StreamML Backup` (o escribe sus nombres reales).
2. En el asistente, completa la URL de API, host/puerto de OBS, escenas y contraseña de OBS. Deja vacía una contraseña ya guardada si no deseas reemplazarla.
3. En StreamML crea una transmisión y genera el código en el paso final **Comprobación** sin salir del flujo. Para una sesión existente también puedes usar **Configuración → Conexiones → Generar código**.
4. Pega el código temporal en el asistente y pulsa **Guardar y vincular**. El código no se persiste.
5. Usa **Comprobar conexión**. Deben aparecer disponibles la API, la vinculación y OBS WebSocket.
6. Pulsa **Iniciar monitorización**. En pocos segundos la vista en vivo comenzará a recibir telemetría.
7. Usa **Detener monitorización** antes de cerrar OBS o cambiar de servidor. La comprobación usa los valores visibles del formulario, aunque todavía no los hayas guardado, y avisa si falta cualquiera de las dos escenas.

La vinculación pertenece a una transmisión concreta. Al guardar un código nuevo con el monitor activo, el asistente detiene y reinicia automáticamente el proceso para cargar el token recién emitido. El paso final de creación y el estado bajo el selector confirman cuándo la transmisión ya tiene un conector vinculado.

## Configurar e iniciar el servidor Docker

La pestaña **Servidor Docker** solicita el dominio HTTPS, certificado TLS, correo/contraseña inicial, orígenes permitidos y, opcionalmente, destinos de retransmisión. Necesita Docker Desktop iniciado. Antes de guardar comprueba que certificado y clave sean PEM válidos y que correspondan entre sí; no basta con que los archivos existan.

Guarda primero los datos y pulsa **Validar Docker Compose**. Después usa **Iniciar o actualizar servicios**. El asistente construye un archivo de entorno temporal solo para el arranque y lo elimina al terminar; no crea un `.env` con secretos permanentes.

La clave privada del certificado no se carga ni se copia: se indica su ruta local para que Docker la monte de solo lectura.

## Secretos y actualización de credenciales

Las contraseñas de OBS, la contraseña administradora, los secretos de token/MediaMTX y el JSON con claves de retransmisión se guardan en el Administrador de credenciales de Windows mediante `keyring`. La interfaz muestra únicamente que una credencial existe; nunca la devuelve ni la coloca en archivos JSON o registros.

Para cambiar una credencial, escribe el valor nuevo en su campo de contraseña y guarda. Para conservar la actual, deja el campo vacío. Los secretos de servidor se generan automáticamente con valores aleatorios seguros cuando se dejan vacíos por primera vez.

## Copias de seguridad

- En la aplicación web, usa **Configuración → Datos → Descargar JSON** para guardar cuenta, ajustes, sesiones y telemetría.
- La configuración no sensible del asistente está en `%LOCALAPPDATA%\StreamML\setup.json`. Puedes copiarla como respaldo; no contiene contraseñas, tokens ni claves RTMP.
- También puedes usar **Ayuda → Descargar copia de configuración**; genera un JSON portátil y confirma explícitamente que no contiene secretos.
- Las credenciales del Administrador de credenciales no se exportan de forma deliberada. Al restaurar en otro equipo, vuelve a introducir las credenciales originales o nuevas desde la GUI.
- Conserva el certificado y su clave privada en el gestor de certificados de tu organización; no los incluyas en repositorios ni en respaldos sin cifrar.

## Problemas comunes

| Problema | Acción recomendada |
| --- | --- |
| API no disponible | Revisa la URL de la API y que el servidor/API esté iniciado. En desarrollo local suele ser `http://127.0.0.1:8000`. |
| OBS no conecta | Abre OBS, activa WebSocket, comprueba `127.0.0.1` y vuelve a guardar la contraseña. Usa `4455` solo si Windows lo tiene disponible; si OBS usa otro puerto (por ejemplo `4855`), escribe exactamente ese mismo valor en el asistente. |
| OBS conecta pero faltan escenas | Crea en OBS exactamente los nombres mostrados como escena en vivo y escena de respaldo, o corrígelos en el formulario. |
| No hay telemetría en Vivo | Genera un código para la transmisión correcta, vincula de nuevo y pulsa **Iniciar monitorización**. Si el registro menciona HTTP 401, el token expiró y debes vincular otro; el conector se detendrá sin saturar OBS. |
| Docker falla en validación | Abre Docker Desktop, revisa que certificado y clave sean PEM válidos, coincidan y que el dominio/orígenes usen HTTPS. |
| Se perdió el asistente local | Ejecuta nuevamente `Abrir-Configuracion-StreamML.cmd`; la configuración no sensible y las credenciales seguras se conservan. |

El registro de diagnóstico del conector se encuentra en `%LOCALAPPDATA%\StreamML\connector.log` y está filtrado para no registrar secretos.

## Actualización

Después de actualizar el código, cierra el asistente y vuelve a ejecutar `scripts\Abrir-Configuracion-StreamML.cmd`. El iniciador repara el paquete dentro de su entorno aislado solo si la importación no es válida, sin borrar ajustes ni credenciales. Para el servidor, abre **Servidor Docker**, valida y pulsa **Iniciar o actualizar servicios**; Compose reconstruye las imágenes y conserva el volumen de la base de datos.

Antes de actualizar producción, descarga la exportación de la aplicación y crea una copia del volumen `api_data`. Después comprueba `/health`, inicia sesión y valida una transmisión de prueba.
