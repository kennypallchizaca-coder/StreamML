# Auditoría de Paridad de Features del Modelo Predictivo

## Objetivo
Determinar si las 19 variables predictivas generadas en tiempo de ejecución (runtime) coinciden semánticamente y en distribución con las calculadas en el dataset de entrenamiento (Ghent).

## 1. Significado Real del Throughput
- **Entrenamiento (Ghent):** Representa el **throughput de descarga** (download capacity proxy) medido por dispositivos móviles recibiendo grandes volúmenes de datos. Mide indirectamente la **capacidad disponible** en la red.
- **Runtime (OBS):** Utiliza `obs_bitrate` o `upload_traffic_mbps`. Ambos representan el **tráfico de subida** codificado por el emisor multimedia.
- **Compatibilidad Semántica:** **INCOMPATIBLE**. El bitrate multimedia no mide la capacidad disponible a menos que la red esté completamente saturada. Alimentar el modelo entrenado para predecir caídas de "capacidad" usando "bitrate constante" genera métricas OOD (Out of Distribution) permanentes.

## 2. Variables Clave y Diferencias

| Variable | Definición (Entrenamiento) | Definición (Runtime) | Unidad | Fuente | Rango Entrenamiento | Rango Runtime | Paridad | Corrección Necesaria |
|---|---|---|---|---|---|---|---|---|
| `throughput_mean, min, max, std, etc.` | Estadísticas del throughput proxy de capacidad | Estadísticas del tráfico/bitrate de subida | Mbps | Descarga (Ghent) vs Subida (OBS) | Fluctuante (0 - 50+ Mbps) | Casi constante | **NO** | Usar métrica de estimación de capacidad real en vez de bitrate. |
| `measurements_count` | `len(hist)` de muestras irregulares (milisegundos) | Frecuencia de recolección ~1 Hz | int | Cálculos | Frecuencias irregulares | ~120 muestras | **SÍ (Estructural)** | Reentrenar con frecuencia alineada al runtime (1 seg). |
| `current_profile` | low=0, medium=1, high=2 | low=1, medium=2, high=3 | int | Reglas sobre p10 | [0, 2] | [1, 3] | **NO** | Alinear diccionarios de clases (se corrigió si se hace reentrenamiento). |
| `required_capacity_mbps` | Fijo a 6.75 para todas las muestras (placeholder) | Dinámico según `current_profile` | Mbps | Umbral superior | 6.75 | 1.35, 3.375, 6.75 | **NO** | Runtime usa lógica correcta; el modelo aprendió con un valor fijo erróneo. |
| `throughput_slope` | Pendiente sobre tiempo (`elapsed_ms`) en ms | Pendiente sobre índice `arange(len(th))` | float | np.polyfit | Depende de ms | Depende de índices (1-120) | **NO** | Runtime debe calcular pendiente sobre marca temporal, no índice. |
| `proportion_below_low/med/high` | % de tiempo por debajo del umbral de capacidad | % de tiempo del bitrate por debajo del umbral | float | % | Amplio espectro | 0.0 constante (bitrate alto) | **NO (Semántica)** | Corregir la fuente de throughput para que evalúe capacidad. |
| `lookback_duration_seconds` | 120 | 120 | seg | Configuración | 120 | 120 | **SÍ** | Ninguna. |

## 3. Conclusión y Acciones
**¿Puede el modelo predictivo continuar ejecutándose?**
No puede tomar decisiones válidas. Las variables de throughput proporcionadas por OBS miden flujo multimedia, no capacidad de red. La escala, la pendiente temporal y el perfil actual (0 vs 1 index) están desalineados respecto a la Fase 1.

**Correcciones aplicadas:**
- Se desacopló y separó la telemetría en `obs_bitrate_mbps`, `network_traffic_upload_mbps` y `predictive_throughput_mbps`.
- Al no existir actualmente una fuente compatible para estimar capacidad predictiva (`predictive_throughput_mbps = None`), el Agente Sombra detecta explícitamente `inference_status = incompatible_feature_source` y previene una predicción inválida.
- La telemetría reactiva continuará guardándose sin alterarse para uso futuro.

**Datos necesarios para un reentrenamiento posterior:**
- Registrar `network_capacity_upload_mbps` derivado de estimadores de ancho de banda como BBR o WebRTC GCC, no solo el bitrate emitido.
- Alinear el mapeo `current_profile` a una sola nomenclatura.
- Calcular `throughput_slope` usando diferencias de tiempo absolutas (segundos) y no saltos de índice.
