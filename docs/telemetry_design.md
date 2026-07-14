# Diseño de Telemetría (Fase 2)

## 1. Métricas a Recopilar y Fuentes Previstas
El sistema capturará en tiempo real una vista consolidada de la red y el estado del stream, obteniendo información de múltiples fuentes:

- **system_network**: `timestamp_utc`, `session_id`, `download_mbps`, `signal_available`
- **vdo_ninja**: `latency_ms`, `jitter_ms`, `packet_loss_percent`
- **obs**: `upload_mbps`, `fps`, `dropped_frames`, `total_frames`, `bitrate_kbps`, `obs_output_active`, `current_profile`
- **mediamtx**: `reconnect_count`, `stream_status`
- **ffmpeg**: `encoder_cpu_percent`

## 2. Reemplazo de proxies públicos
En la Fase 1, los modelos se entrenaron con datos sintéticos y públicos (ej. métricas genéricas de red en repositorios RTR-NetzTest). En esta fase:
- `latency_ms`, `jitter_ms` y `packet_loss_percent` extraídas directamente de VDO.Ninja (WebRTC) reemplazarán las estimaciones de latencia y ping genéricas.
- `upload_mbps` calculado mediante el flujo real de OBS Studio (RTMP/SRT) reemplazará los benchmarks genéricos de velocidad de subida móvil.

## 3. Frecuencia de Registro
Se configura una **frecuencia recomendada de registro de 1 segundo**. Esto permite a los modelos de machine learning reaccionar casi en tiempo real (modelo reactivo) y recolectar una ventana temporal de alta resolución para prever caídas a corto plazo (modelo predictivo). Esta frecuencia será parametrizable en la arquitectura final.

## 4. Identificación y Aislamiento de Sesiones
- **Identificación:** Cada transmisión iniciada recibirá un identificador único global (`session_id`) generado al iniciar el script o agente.
- **Aislamiento:** Este `session_id` se inyectará en todas las métricas de todas las fuentes durante esa sesión. Esto evitará mezclar datos de transmisiones distintas (ej. si ocurre un reinicio del agente) y asegura que las secuencias predictivas temporales se construyan solo con datos continuos de la misma sesión.

## 5. Evaluación de Pérdidas y Degradación
Las siguientes variables servirán para evaluar de forma directa y fehaciente las pérdidas y degradaciones del streaming IRL:
- **`dropped_frames` (acumulado)** y su diferencial temporal.
- **`fps`** actuales generados vs esperados.
- **`packet_loss_percent`** de VDO.Ninja.
- **`reconnect_count`** del servidor MediaMTX y el `stream_status`.

## 6. Pérdida Completa de Señal (Fallback Determinista)
El campo `signal_available` (bool) monitoreado mediante `system_network`, y la **ausencia prolongada de datos** desde OBS/VDO.Ninja, se utilizarán posteriormente mediante reglas deterministas estables para activar de inmediato el fallback del sistema, sin depender de los umbrales estadísticos de los modelos de Machine Learning (los cuales requieren flujo constante de datos para predecir).
