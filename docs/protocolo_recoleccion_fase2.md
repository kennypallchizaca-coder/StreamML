# Protocolo de Recolección de Telemetría (Fase 2)

## Objetivo de la Recopilación
Construir un dataset propio de transmisiones reales mediante OBS para entrenar y validar posteriormente los modelos de Machine Learning (reactivo y predictivo) en entornos de streaming en vivo, asegurando que estén ajustados a la telemetría verdaderamente disponible y representativa.

## Diferencia entre Bitrate, Tráfico y Capacidad Disponible
- **Bitrate (OBS):** Es la tasa de codificación de video objetivo seleccionada por el usuario o el agente. Mide cuánta información genera el codificador multimedia.
- **Tráfico (Upload/Download):** Es el tráfico real que fluye por la interfaz de red en un momento dado. Está limitado por el bitrate de codificación.
- **Capacidad Disponible (Throughput de red):** Es el ancho de banda máximo que la red podría soportar en ese instante. **OBS no mide la capacidad disponible.** Usar el bitrate de OBS como proxy de la capacidad genera métricas permanentemente "Fuera de Distribución", ya que un bitrate constante de 5 Mbps no implica que la red solo tenga 5 Mbps de capacidad, ni exhibe las mismas variaciones estadísticas que una prueba de descarga en bruto.

## Campos Registrados
Por cada segundo de sesión, se registran variables clave:
- `timestamp_utc` y `elapsed_seconds`: Cronometría temporal.
- `obs_connected` y `stream_active`: Estado general.
- `obs_bitrate_kbps`, `fps`, `dropped_frames`, `total_frames`: Rendimiento del emisor multimedia.
- `network_traffic_upload_mbps` y `network_traffic_download_mbps`: Tráfico local en interfaces.
- `latency_ms`: Retardo estimado (si está habilitado/disponible).
- `current_profile_name`, `current_profile_code`, `required_capacity_mbps`: Perfil manual operando (ej: high = 3, 6.75 Mbps).
- `experimental_condition`: Condición experimental bajo prueba (stable, bandwidth_reduction, etc.).
- `event_label`: Evento actual o etiqueta (stable, freeze, etc.).
- `action_applied`: 'none' (el agente solo recopila).

## Procedimiento de cada Sesión
1. Iniciar **MediaMTX** (el servidor RTMP local).
2. Abrir **VDO.Ninja** u otra cámara y capturarla en **OBS**.
3. Iniciar la **Transmisión en OBS**.
4. Ejecutar el script recolector: `python scripts/run_data_collection_session.py --duration 180 --profile high --condition stable`.
5. Durante la ejecución, los modelos permanecerán desactivados. La telemetría se volcará segundo a segundo a `data/telemetry/raw/`.

## Etiquetado de Eventos (Opcional)
Para agregar meta-etiquetas de eventos manuales, sin tocar el CSV, usar:
```bash
python scripts/label_session.py --session_id <SESSION_ID> \
  --label freeze --start_utc "2026-07-14T10:00:00Z" \
  --end_utc "2026-07-14T10:00:30Z" --severity high --notes "Pérdida de paquetes en OBS"
```
Estos eventos se guardan en `data/telemetry/events/`.

## Operación Pasiva
El control automático y los modelos ML se configuran deliberadamente en **false**. El objetivo es recolectar datos "ground truth" puros sin que el agente altere la escena ni el bitrate por sí solo, lo cual es vital para el próximo reentrenamiento de las fases venideras. Las degradaciones de red se introducirán **externamente** (ej: NetLimiter, Clumsy) en pruebas posteriores, no mediante el agente.
