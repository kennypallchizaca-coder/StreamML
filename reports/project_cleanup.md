# Auditoría de preparación para GitHub y despliegue

Fecha: 2026-07-17

## Objetivo y alcance

Esta auditoría organiza el repositorio para publicación y prepara su
configuración operativa sin retirar funcionalidades ni modificar los contratos,
datasets procesados o modelos publicados. No constituye una afirmación de que
una transmisión real ya fue certificada: esa última etapa requiere OBS, teléfono,
DNS/TLS, red móvil y credenciales RTMP(S) reales.

## Estructura conservada

| Área | Responsabilidad |
|---|---|
| `apps/api/` | API FastAPI, sesiones, telemetría, inferencia y orquestación |
| `apps/frontend/` | interfaz React compilada con lockfile npm |
| `apps/connector/` | conector local autenticado para OBS WebSocket |
| `apps/media/` | fallback H.264/AAC y retransmisión supervisada con FFmpeg |
| `src/streamml/` | dominio ML, datos, modelos, seguridad y servicios compartidos |
| `data/processed/` y `models/registry/` | datasets y release verificable necesarios para reproducibilidad |
| `infrastructure/` y `deployment/` | Docker, nginx, MediaMTX y configuración de despliegue |

No se movieron directorios solo por estética: las rutas de imports, Docker,
scripts, notebooks y pruebas existentes ya siguen una separación coherente y
un cambio de ubicación incrementaría el riesgo sin mejorar el producto.

## Limpieza y artefactos

- Cachés Python, `node_modules`, build del frontend, bases SQLite locales,
  descargas originales, archivos temporales, logs y secretos quedan excluidos
  por `.gitignore`.
- `.dockerignore` también excluye `.env` y entornos equivalentes para que los
  secretos no entren ni siquiera al contexto de build.
- Los CSV procesados, el manifiesto de fuentes, los contratos y los artefactos
  junto a los modelos se conservan intencionalmente. Son parte del release
  verificable, no duplicados temporales.
- `output/` estaba vacío, sin referencias en código ni scripts y no formaba
  parte del repositorio; fue eliminado sin afectar el proyecto.

## Mejoras de publicación y operación

- `README.md` documenta requisitos, instalación, desarrollo local, frontend,
  conector, despliegue, seguridad y límites conocidos.
- `.env.example`, `deployment/.env.example` y `apps/frontend/.env.example`
  contienen únicamente nombres, placeholders o valores públicos.
- `requirements.txt` fija también las versiones usadas para ejecutar notebooks;
  el runtime productivo mínimo permanece separado en `requirements-api.txt` y
  el conector usa su propio `pyproject.toml`.
- El cliente OBS se denomina `ObsClient`; `ReadOnlyObsClient` se conserva como
  alias de compatibilidad para importaciones anteriores.
- `.github/workflows/ci.yml` ejecuta pruebas, compilación Python, release,
  demo, wheel del conector, control de secretos, configuración Compose, auditoría
  npm y build del frontend en cada `push` y `pull_request`.
- `SECURITY.md` documenta el reporte responsable de vulnerabilidades.
- Compose usa logs rotativos, apagado ordenado, procesos init, filesystem de
  solo lectura donde aplica y la versión validada `bluenviron/mediamtx:1.19.2`.
- Los escritores de artefactos verificables emiten UTF-8 con LF explícito. Así
  los hashes del release son idénticos en Windows, Linux y GitHub Actions.

## Verificaciones realizadas

| Comprobación | Resultado |
|---|---|
| `python -m pytest -q` | 71 pruebas aprobadas |
| `python -m compileall -q apps src scripts` | correcta |
| `python scripts/verify_release.py` | `STREAMML RELEASE VERIFIED` |
| `python scripts/check_no_secrets.py --history` | correcta, sin firmas conocidas en el historial alcanzable |
| `python -m pip check` | sin requisitos rotos |
| `python -m pip wheel --no-deps ... apps/connector` | wheel `streamml-connector` construido |
| `npm ls --depth=0` y `npm audit --audit-level=high` | árbol resuelto; 0 vulnerabilidades reportadas |
| `npm test`, `npm run lint` y `npm run build` | 12 pruebas aprobadas, lint limpio y compilación correcta; advertencia informativa por el chunk HLS cargado bajo demanda |
| `docker compose ... config --quiet` | configuración válida de API, frontend, MediaMTX, fallback, worker y nginx |
| Réplica Linux del job Python | instalación del conector incluida; hashes y modelos verificados fuera de Windows |
| `git diff --check` | sin errores de whitespace |

## Condiciones externas antes de producción

1. Configurar DNS, certificados TLS válidos y firewall para TCP 80/443 y UDP
   8189; no exponer OBS ni los puertos internos de MediaMTX.
2. Generar secretos únicos y credenciales reales en `deployment/.env`, que debe
   permanecer ignorado y con permisos restringidos.
3. Crear las escenas OBS configuradas, probar WebSocket en loopback y confirmar
   que el modo de salida permite cambios de perfil durante una codificación real.
4. Probar VDO.Ninja → OBS → MediaMTX → WHEP/HLS, pérdida y recuperación de la
   fuente, fallback MP4, retorno al vivo y cada destino RTMP(S).
5. Hacer backup y restauración de SQLite, prueba de renovación TLS, prueba de
   carga y aislamiento entre usuarios antes de abrir el servicio al público.

La guía operativa completa se mantiene en `docs/deployment.md`.
