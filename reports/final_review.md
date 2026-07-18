# Revisión final funcional y técnica

Fecha: 2026-07-18

## Conclusión

El objetivo académico y funcional está cumplido: StreamML recibe telemetría real
de OBS, ejecuta los modelos reactivo y predictivo, aplica la política autónoma y
controla perfiles y escenas mediante un conector autenticado. La afirmación de
preparación completa para producción queda **parcialmente cumplida** porque una
prueba aislada no reemplaza la certificación física con teléfono, red móvil,
DNS/TLS confiable y credenciales reales de Kick, YouTube, Twitch o Facebook.

## Errores corregidos en la revisión

- Los estados `ready`, `offline` y `completed` se presentaban como si todos
  significaran "Finalizada". Ahora tienen etiquetas diferentes y solo una
  emisión realmente activa aparece como "En vivo".
- Dashboard e historial mantenían reglas distintas para determinar una sesión
  activa. La regla se centralizó y quedó cubierta por pruebas.
- Historial afirmaba "Ninguna" alerta sin una fuente que lo demostrara y
  describía toda una sesión a partir de una sola inferencia. Ahora muestra `--`
  cuando no hay evidencia y explica que el resumen procede de la última
  inferencia disponible.
- Alertas marcaba elementos derivados como "Revisada" y atribuía problemas
  observados sin una entidad de revisión. Ahora informa únicamente la
  recomendación registrada por el modelo y usa mensajes vacíos neutrales.
- Los comandos PowerShell del README omitían el prefijo `./` equivalente
  (`.\`) requerido para ejecutar el Python del entorno local. Todos usan ahora
  `.\.venv311\Scripts\python.exe`.

## Limpieza realizada

Se eliminaron nueve archivos sin importaciones ni uso en la aplicación:

- `CircularGauge.tsx` y `MetricCard.tsx` del dashboard anterior.
- `alert-dialog.tsx`, `checkbox.tsx`, `collapsible.tsx`, `popover.tsx`,
  `radio-group.tsx`, `scroll-area.tsx` y `textarea.tsx` de la plantilla no usada.

También se retiraron ocho dependencias directas `@radix-ui/*` redundantes. Los
controles activos importan ahora el paquete `radix-ui` ya utilizado por el
sistema de componentes. No se eliminaron modelos, datasets, migraciones,
scripts operativos ni funcionalidades activas.

En la limpieza final se retiró además `skeleton.tsx`, que no tenía referencias.
`sidebar.tsx` y `sheet.tsx` se conservan porque forman parte activa de la
navegación adaptable utilizada por `AppShell`; el menú desplegable también se
mantiene por ser funcionalidad en uso.

## Evidencia funcional

- La sesión real `KICK2` mostró OBS conectado, salida activa, 30 FPS, bitrate,
  frames, latencia, jitter, pérdida y capacidad de subida.
- Se registraron 2.136 muestras continuas de telemetría.
- Modelo reactivo: 2.136 inferencias ejecutadas.
- Modelo predictivo: primeras 600 solicitudes bloqueadas correctamente hasta
  completar la ventana; después, 1.536 inferencias ejecutadas.
- El agente quedó en perfil `high` con decisión `maintain`, margen de capacidad
  y política de histéresis activos.
- La base contiene un comando `activate_backup` y un `restore_live`, ambos
  confirmados como `completed` por el conector OBS.
- La GUI mostró **EN VIVO** y "Telemetría recibida"; no hubo errores de consola.
- El monitor presenta por separado la decisión final del agente, la recomendación
  `low/medium/high` del modelo reactivo y la salida `maintain/downgrade_needed`
  con probabilidad del modelo predictivo, incluidos sus estados y variables.
- La pantalla Modelos ML presenta conjunto de prueba, baseline, matriz de
  confusión, algoritmos comparados, importancia de variables y limitaciones.
- Cada inferencia incluye evidencia observada y cada acción del agente conserva
  un código de razón y un estado operacional auditables.
- La navegación eliminó indicadores duplicados, el monitor consolidó la
  telemetría y los detalles extensos de modelos y variables usan divulgación
  progresiva. Nexa dispone de cinco poses pixel-art WebP optimizadas y accesibles.
- La auditoría reproducible detectó 17 sesiones predictivas, 93,87% de filas con
  vectores repetidos y 100% de solapamiento entre ventanas adyacentes; estas
  limitaciones quedan visibles en vez de ocultarse detrás de la métrica agregada.
- En el replay determinista, el agente completo obtuvo 92,53/100 frente a 58,83
  del perfil fijo y redujo la interrupción proxy de 65 a 3 segundos. Es una
  prueba de regresión sintética, no evidencia física de QoE.

## Pruebas ejecutadas

| Verificación | Resultado |
|---|---|
| `python -m pytest -q` | 76 aprobadas |
| Ruff | limpio |
| `compileall` | correcto |
| release de modelos | `STREAMML RELEASE VERIFIED` |
| demo de inferencia | reactivo `high`; predictivo `maintain` |
| frontend Vitest | 17 aprobadas |
| ESLint | limpio, cero advertencias |
| TypeScript y Vite | compilación correcta |
| `npm audit --omit=dev` | 0 vulnerabilidades |
| `pip check` | sin requisitos rotos |
| control de secretos e historial | aprobado |
| Docker Compose | configuración válida |
| réplica HTTPS de producción | API, frontend, MediaMTX, worker y nginx saludables |
| controles de producción | `production_ready: true`, acceso anónimo 401 |
| puertos de medios aislados | RTMP, HLS y WHEP/TCP accesibles solo en loopback |
| registros de contenedores | 0 coincidencias ERROR/Traceback/FATAL |

La GUI se comprobó en escritorio y a 390 px en dashboard, historial,
configuración, creación y monitoreo, sin desbordamiento horizontal. Se probaron
navegación, pestañas, búsqueda, detalle histórico, tema claro/oscuro y el
asistente local. El tema global mantiene bordes cuadrados y tokens compartidos.

## Comparación con los requisitos originales

| Requisito | Estado | Evidencia |
|---|---|---|
| Captura móvil por VDO.Ninja y uso en OBS | Implementado, certificación física pendiente | URLs `push`/`view`, validación y fuente de navegador; el estado del teléfono depende de eventos externos de VDO.Ninja |
| Telemetría actual de OBS y red | Cumplido | 2.136 muestras reales y métricas visibles |
| Modelo reactivo `low/medium/high` | Cumplido | release verificado e inferencia real ejecutada |
| Predictivo de 10 minutos `maintain/downgrade_needed` | Cumplido | ventana de 600 muestras e inferencias ejecutadas |
| Agente con seguridad, histéresis y cooldown | Cumplido | estado persistido y decisiones reales |
| Cambio preventivo de calidad | Implementado; falta una prueba física degradando la red | comandos autenticados y política probada unitariamente |
| Escena de respaldo y recuperación | Cumplido en OBS | comandos de activación y restauración completados |
| Fallback FFmpeg hacia plataforma externa | Implementado; prueba real pendiente | worker saludable y pruebas unitarias; no se usaron claves RTMP reales |
| GUI centralizada y segura | Cumplido | dashboard y asistente local, keyring de Windows, validaciones y persistencia |
| Despliegue productivo | Técnicamente validado, go-live pendiente | réplica Docker saludable; faltan DNS/TLS público, firewall y plataforma real |

## Riesgos y limitaciones conocidos

- La fuente predictiva contiene solo 17 sesiones largas y fuerte desbalance; una
  métrica perfecta no demuestra generalización en redes móviles reales.
- La sonda HTTP mide la ruta OBS-servidor, no la calidad WebRTC interna entre el
  teléfono y VDO.Ninja.
- La vista local actual no recibe siempre un evento verificable de VDO.Ninja;
  por eso el teléfono permanece "No disponible" aunque OBS pueda consumir la
  fuente. El panel no inventa ese estado.
- `hls.js` se carga de forma diferida pero su chunk minificado supera 500 kB;
  Vite emite una advertencia de tamaño no bloqueante.
- Deben probarse físicamente pérdida/recuperación, cambio de bitrate mientras el
  encoder está activo, fallback FFmpeg y recepción final en cada plataforma.

## Comandos exactos

Instalación limpia en PowerShell:

```powershell
Set-Location "C:\Users\kenny\OneDrive\Documents\STREAM-AI\Adaptive-Streaming-ai"
py -3.11 -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install --upgrade pip
.\.venv311\Scripts\python.exe -m pip install -r requirements.txt -e apps/connector
Set-Location apps\frontend
npm ci
Set-Location ..\..
Copy-Item .env.example .env
```

Ejecución local en tres terminales desde la raíz:

```powershell
.\.venv311\Scripts\python.exe -m uvicorn apps.api.main:app --reload --env-file .env
```

```powershell
Set-Location apps\frontend
npm run dev
```

```powershell
.\scripts\Abrir-Configuracion-StreamML.cmd
```

Pruebas y compilación:

```powershell
.\.venv311\Scripts\python.exe -m pytest -q
.\.venv311\Scripts\python.exe -m ruff check apps src scripts tests
.\.venv311\Scripts\python.exe -m compileall -q apps src scripts
.\.venv311\Scripts\python.exe scripts\verify_release.py
.\.venv311\Scripts\python.exe scripts\demo_models.py
.\.venv311\Scripts\python.exe scripts\check_no_secrets.py --history
Set-Location apps\frontend
npm test
npm run lint
npm run build
npm audit --omit=dev --audit-level=high
Set-Location ..\..
docker compose --env-file deployment/.env.example -f infrastructure/docker/docker-compose.yml config --quiet
```

Despliegue, después de completar `deployment/.env` con secretos, dominio y
certificados reales:

```powershell
docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml up -d --build --wait
docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml ps
```

Detención conservando datos:

```powershell
docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml down
```
