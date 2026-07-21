# Política de seguridad

## Configuración soportada

La configuración soportada es la rama `main` actual, usando el release de modelos
fijado, la configuración de Docker Compose y los archivos de ejemplo de entorno
incluidos en este repositorio. No exponer OBS WebSocket, los listeners de control
de MediaMTX ni un archivo `.env` sin protección a la internet pública.

## Reportar una vulnerabilidad

No incluir credenciales, claves de transmisión, datos personales ni detalles de
exploit en un issue público. Usar la función de reporte privado de vulnerabilidades
de GitHub para este repositorio cuando esté habilitada; de lo contrario, contactar
a un mantenedor a través del perfil del propietario del repositorio y proporcionar
solo la información mínima necesaria para establecer un canal seguro.

Si una credencial pudo haber sido expuesta, rotarla inmediatamente. Eliminarla
del último commit no la elimina del historial de Git.

## Protecciones del repositorio

- `.env`, claves, credenciales, bases de datos en ejecución, cachés y descargas
  de datos crudos están ignorados por Git y excluidos del contexto de build de Docker.
- `scripts/check_no_secrets.py --history` verifica el historial alcanzable de Git
  en busca de firmas comunes de claves privadas y tokens, sin mostrar valores
  candidatos.
- CI ejecuta la verificación antes de aceptar builds. Esto complementa la
  gestión de secretos y el escaneo de secretos de GitHub; no es un sustituto
  de ninguno de los dos.
