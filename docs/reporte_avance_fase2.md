# Avance de Presentación — Streaming Adaptativo mediante Machine Learning

**Integrantes:** Alexis Guamán y Cinthya Ramón  
**Fecha:** 15 de julio de 2026  
**Fase actual:** Fase 2 — Recolección de telemetría real

---

## 1. Objetivo general

Desarrollar un sistema de Machine Learning capaz de analizar las condiciones de red en tiempo real durante una transmisión de video en vivo (streaming IRL) y recomendar ajustes automáticos de calidad (bitrate, resolución, FPS) para mantener la continuidad del stream.

## 2. Trabajo completado

### Fase 1 — Modelos offline (completada)
- Búsqueda y descarga de datasets públicos de mediciones de red.
- Preparación de datos: limpieza, normalización, creación de pseudoetiquetas.
- Diseño de ventanas temporales de 120 segundos para el modelo predictivo.
- Entrenamiento y evaluación de múltiples algoritmos.
- Validación agrupada por sesiones (`GroupKFold`, 5 folds, 27 sesiones).
- Selección de modelos finales.
- Congelación de artefactos en `models/phase1_final_release/`.
- Pruebas de recarga, reproducibilidad e integridad (hashes SHA-256).
- Script de verificación automatizado (`verify_phase1_release.py`).
- 38 pruebas unitarias pasando correctamente.

### Fase 2 — Integración y telemetría (en progreso)
- Integración de VDO.Ninja como fuente de cámara remota vía WebRTC.
- Configuración de OBS Studio con WebSocket para extracción de métricas.
- Configuración de MediaMTX como servidor de restreaming RTMP.
- Desarrollo del recolector de telemetría (`TelemetryCollector`).
- Desarrollo del recolector de sesiones (`SessionDataCollector`).
- Desarrollo del colector OBS (`OBSTelemetryCollector`).
- Desarrollo del buffer temporal (`TelemetryBuffer`).
- Desarrollo del agente sombra (`ShadowAgent`).
- Implementación del script de recolección de datos por sesión.
- Implementación del etiquetado de sesiones.
- Validación exitosa de la primera sesión estable.

## 3. Arquitectura actual

```text
┌─────────────────┐
│  VDO.Ninja       │  ← Cámara móvil (WebRTC)
│  (Smartphone)    │
└────────┬────────┘
         │ WebRTC
┌────────▼────────┐
│  OBS Studio      │  ← Composición + codificación
│  (WebSocket API) │
└────────┬────────┘
         │ RTMP
┌────────▼────────┐
│  MediaMTX        │  ← Servidor de restreaming
│  (localhost)     │
└────────┬────────┘
         │
┌────────▼────────┐
│  Recolector de   │  ← Captura métricas cada segundo
│  Telemetría      │
└────────┬────────┘
         │
┌────────▼────────┐
│  Modelos ML      │  ← Shadow Mode (observan, no actúan)
│  (Desactivados)  │
└─────────────────┘
```

## 4. Modelos desarrollados

### Modelo reactivo
- **Algoritmo:** DecisionTreeClassifier
- **Entrada:** `upload_mbps`, `download_mbps`, `latency_ms`
- **Salida:** Perfil recomendado (`low`, `medium`, `high`)
- **Tipo de problema:** Clasificación multiclase

### Modelo predictivo
- **Algoritmo:** RandomForestClassifier
- **Entrada:** 19 features estadísticos de una ventana de 120 segundos
- **Salida:** `maintain` o `downgrade_needed`
- **Tipo de problema:** Clasificación binaria

## 5. Métricas principales de la Fase 1

| Métrica | Reactivo | Predictivo |
|---|---|---|
| Algoritmo | DecisionTree | RandomForest |
| Macro F1 (test) | 0.9977 | 0.4950 |
| Macro F1 (validación) | — | 0.5952 |
| Mejor baseline | — | 0.4799 |
| Generalization gap | — | 0.1002 |
| Recall downgrade (test) | — | 0.3333 |
| Falsos positivos | — | 21 |
| Falsos negativos | — | 4 |
| Umbral | — | 0.55 |

## 6. Integración VDO.Ninja → OBS → MediaMTX

La cadena de transmisión fue establecida con éxito:
1. **VDO.Ninja** captura video desde la cámara del teléfono y lo transmite vía WebRTC.
2. **OBS Studio** recibe el flujo como fuente de navegador, compone la escena y codifica el video.
3. **OBS** retransmite vía RTMP hacia **MediaMTX** ejecutándose localmente.
4. El recolector de telemetría extrae métricas cada segundo desde OBS (WebSocket) y la red del sistema.

## 7. Telemetría recopilada

El sistema de recolección captura segundo a segundo:
- **Red:** `upload_mbps`, `download_mbps`, `latency_ms`, `jitter_ms`, `packet_loss_percent`
- **Video (OBS):** `fps`, `bitrate_kbps`, `dropped_frames`, `total_frames`
- **Sistema:** `encoder_cpu_percent`, `obs_output_active`, `current_profile`
- **Estado:** `stream_status`, `reconnect_count`, `signal_available`

Los datos se guardan en `data/telemetry/` con metadatos JSON asociados.

## 8. Correcciones realizadas

- Corrección de la lógica de cálculo de bitrate real vs. bitrate configurado de OBS.
- Separación clara entre `upload_traffic_mbps` (tráfico de red real) y `obs_bitrate_kbps` (configuración de OBS).
- Auditoría de paridad entre features de entrenamiento y features de runtime.
- Validación de timestamps y orden cronológico en las muestras.

## 9. Resultado de la sesión estable

Se ejecutó una sesión de recolección controlada:

| Parámetro | Valor |
|---|---|
| Duración solicitada | 60 segundos |
| Muestras registradas | 60 |
| Filas inválidas | 0 |
| Errores de timestamp | 0 |
| Estado de validación | `valid` |
| Frames omitidos | 0 |
| Acciones automáticas | Ninguna (`action_applied = none`) |
| Modelos ejecutados | No (`models_executed = false`) |

## 10. Problema detectado: compatibilidad semántica

Se identificó que las features usadas durante el entrenamiento offline (basadas en datasets públicos) no son idénticas a las features que produce el recolector de telemetría local. En particular:
- El entrenamiento usó `throughput_mbps` (descarga como proxy de capacidad).
- El runtime produce `upload_traffic_mbps` (subida real del sistema).

Esta diferencia semántica fue documentada en `docs/auditoria_paridad_features.md` y requiere un puente de adaptación o reentrenamiento con datos locales para la inferencia real.

## 11. Estado actual de los modelos

- Los modelos de la Fase 1 están **entrenados, congelados y verificados**.
- Durante la recolección actual, los modelos **permanecen desactivados**.
- El sistema solo **observa y registra** (no toma decisiones).
- El bitrate reportado por OBS **no se usa** como medida de capacidad disponible.

## 12. Trabajo pendiente

- [ ] Implementar puente semántico entre features de entrenamiento y features de runtime.
- [ ] Recolectar suficiente telemetría real para reentrenamiento.
- [ ] Activar Shadow Mode con predicciones (sin control automático).
- [ ] Validar predicciones del Shadow Mode contra eventos reales.
- [ ] Evaluar si los modelos actuales son transferibles o requieren reentrenamiento completo.
- [ ] Diseñar mecanismo de fallback robusto.
- [ ] Implementar control automático (solo después de validación exhaustiva).

## 13. Tabla de estado de componentes

| Componente | Estado |
|---|---|
| Modelo reactivo | Entrenado y congelado |
| Modelo predictivo | Entrenado y congelado |
| Integración OBS | Funcionando |
| MediaMTX | Funcionando |
| Recolección de telemetría | Funcionando |
| Etiquetado de sesiones | Funcionando |
| Inferencia con datos reales | Pendiente |
| Control automático | Desactivado |
| Producción | No disponible |

## 14. Conclusión del avance

El proyecto ha completado satisfactoriamente la Fase 1 (modelos offline) y se encuentra en la Fase 2 (integración y telemetría real). Se logró:
1. Establecer la cadena completa de transmisión (VDO.Ninja → OBS → MediaMTX).
2. Implementar un sistema de recolección de telemetría funcional y validado.
3. Ejecutar la primera sesión de recolección con 0 errores.
4. Identificar y documentar la brecha semántica entre features de entrenamiento y runtime.

El siguiente paso inmediato es la activación del Shadow Mode para evaluar las predicciones de los modelos contra la realidad observada, sin intervención automática sobre la transmisión.
