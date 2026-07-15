# Arquitectura de la Fase 2: Modo Sombra

## Flujo de video previsto
El flujo de transmisión audiovisual operará de la siguiente manera:
1. **Teléfono móvil** (Cámara y transmisión origen)
2. → **VDO.Ninja** (Transferencia mediante WebRTC)
3. → **OBS** (Recibe VDO.Ninja como fuente de navegador y compone la escena)
4. → **Salida RTMP de OBS** (Emisión del video codificado)
5. → **Servidor o máquina virtual** (Entorno de procesamiento)
6. → **MediaMTX** (Servidor RTSP/RTMP intermedio)
7. → **FFmpeg** (Procesamiento o retransmisión)
8. → **Plataformas de streaming** (Destino final como Twitch o YouTube)

## Flujo de telemetría previsto
Paralelamente, el flujo de datos para los modelos de Machine Learning funcionará así:
1. **Red local + OBS** (Generación de métricas puras)
2. → **Recolector de telemetría** (Script que captura estadísticas de red y hardware)
3. → **Archivo de sesión** (Almacenamiento persistente en disco en `data/telemetry/`)
4. → **Buffer temporal de 120 segundos** (Ventana deslizante de memoria)
5. → **Modelos finales de la Fase 1** (Inferencia sobre el buffer)
6. → **Predicciones en modo sombra** (Generación de recomendaciones sin impacto)
7. → **Registro de resultados** (Almacenamiento de las predicciones en el esquema de telemetría)

## Aclaraciones Importantes
- **VDO.Ninja** entrega el video a **OBS** mediante el protocolo **WebRTC**, asegurando baja latencia en la red local.
- **OBS** genera una salida **RTMP** completamente independiente hacia el servidor.
- Durante las primeras pruebas de la Fase 2, **los modelos no controlarán OBS de ninguna manera**. Se aislará completamente la inferencia del flujo de video.
- El sistema **solo registrará recomendaciones** basadas en las predicciones (Modo Sombra / Shadow Mode), permitiendo evaluar la efectividad sin arriesgar la transmisión real.
- El **control automático** se implementará en una etapa posterior, una vez que el modo sombra demuestre confiabilidad.
- La **pérdida total de señal** (desconexión) deberá manejarse posteriormente mediante reglas deterministas y un mecanismo de fallback robusto, ya que los modelos predictivos están diseñados para degradaciones, no para cortes absolutos.

## Componentes del Sistema

| Componente | Responsabilidad | Entrada | Salida | Protocolo | Ubicación | Dependencia | Estado Actual |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Teléfono móvil** | Captura y envío inicial de video | Cámara física | Video en vivo | WebRTC | Local (Origen) | N/A | Pendiente |
| **VDO.Ninja** | Enlace peer-to-peer de video | Video del móvil | Stream web | WebRTC | Internet / LAN | Teléfono móvil | Pendiente |
| **OBS** | Composición y codificación | Fuente VDO.Ninja | Stream RTMP | RTMP | Máquina local | VDO.Ninja | Pendiente |
| **Recolector de red** | Captura de métricas (upload, download, latency) | OS / Interfaces | Métricas brutas | API Local | Máquina local | Red física | Pendiente |
| **Recolector de OBS** | Captura de métricas (FPS, dropped frames, bitrate) | OBS WebSocket | Métricas OBS | WebSocket | Máquina local | OBS | Pendiente |
| **Buffer de 120 segundos** | Acumular ventana de tiempo para el modelo | Métricas recolectadas | 19 variables calculadas | Memoria (Python) | Máquina local | Recolectores | Pendiente |
| **Modelo reactivo** | Recomendar perfil según instante actual | upload, download, latency | Perfil (low/medium/high) | Pipeline ML | Máquina local | Recolectores | ✅ Fase 1 (Completo) |
| **Modelo predictivo** | Anticipar degradación inminente | 19 variables de buffer | maintain / downgrade | Pipeline ML | Máquina local | Buffer 120s | ✅ Fase 1 (Completo) |
| **Agente en modo sombra** | Orquestar flujo y registrar inferencias | Métricas y Modelos | Logs / Archivos CSV | Archivos Locales | Máquina local | Modelos | Pendiente (Diseño) |
| **Almacenamiento de telemetría** | Persistir datos históricos para Fase 3 | Salida del Agente | Archivo CSV | Disco local | Máquina local | Agente sombra | Pendiente |
| **MediaMTX** | Servidor de puente para distribución | Stream RTMP | Stream RTMP/RTSP | RTMP/RTSP | Servidor | OBS | Pendiente |
| **FFmpeg** | Transcodificación y retransmisión | Stream de MediaMTX | Stream adaptado | RTMP | Servidor | MediaMTX | Pendiente |
| **Plataformas de streaming** | Distribución final al usuario | Stream final | Video público | RTMP/HLS | Nube | FFmpeg / Servidor | Pendiente |


## OBS WebSocket (Modo Solo Lectura)
- **OBS WebSocket** se utiliza exclusivamente para lectura (recolección de telemetría como FPS, bitrate, y frames perdidos).
- Las credenciales de conexión se cargan de forma segura mediante variables de entorno (archivo .env), y nunca se exponen en repositorios.
- Las métricas de OBS se incorporan al mismo archivo de sesión CSV, junto con las métricas de red locales, de forma asíncrona.
- Ninguna predicción o modelo modifica OBS. El sistema opera garantizando que no existan llamadas de control de ningún tipo.
- El itrate_kbps se calcula con alta precisión y de forma no acumulativa mediante las diferencias de outputBytes reportadas periódicamente.
