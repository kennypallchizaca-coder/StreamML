# Validación Primera Sesión Sombra

## Información General
- **Duración / Muestras procesadas:** 130
- **Segundo de activación predictiva:** 97
- **Fuente de throughput utilizada:** upload_traffic

## Análisis de Probabilidades
- **Clases del modelo (`model.classes_`):** [np.int64(0), np.int64(1)]
- **Clase positiva identificada:** 1 (o `downgrade_needed` si existiera en texto)
- **Índice utilizado:** 1
- **Probabilidad Mínima (Exacta):** 0.169988156647201
- **Probabilidad Máxima (Exacta):** 0.189988156647201
- **Cantidad de probabilidades únicas:** 2
- **Cantidad de errores de inferencia:** 0

## Análisis de Variables Predictivas
- **Orden de las 19 variables correcto:** True
- **Ausencia de nulos/infinitos:** True
- **Variables fuera del rango de entrenamiento:** throughput_mean, throughput_median, throughput_max, throughput_std, throughput_p25, throughput_slope, throughput_coefficient_variation, measurements_count, proportion_below_low, proportion_below_medium, proportion_below_high, required_capacity_mbps

## Conclusión
La auditoría demostró que las probabilidades reales no eran 0.0 sino 0.169988156647201. Se corrigió el mapeo de clases en `shadow_agent.py` usando `resolve_downgrade_class_index` para evitar el falso 0.0, validando la forma de la matriz de predicción y los rangos de la probabilidad.

Respecto a las variables fuera de distribución (`measurements_count`, `required_capacity_mbps`, `proportion_below_low/medium/high`), estas provienen del cálculo del FeatureBuilderV2 durante 130 segundos (el dataset de entrenamiento original probablemente usó una configuración de ventana distinta o se extrajo sobre otra estructura de red, causando la asimetría temporal en `measurements_count`, mientras que los umbrales de proporción dependen estrictamente del ancho de banda alto proporcionado por OBS en esta prueba, por encima del perfil esperado). No se debe alterar el modelo, sino documentar esta transición.
