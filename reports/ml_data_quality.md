# Auditoría reproducible de datos ML

Este informe se genera directamente desde los CSV procesados y los splits oficiales. No modifica los datos ni los modelos.

## Resumen

| Dataset | Filas/ventanas | Sesiones | Vectores únicos | Filas duplicadas por features |
|---|---:|---:|---:|---:|
| Reactivo | 26686 | 26686 | 26686 | 0 |
| Predictivo | 4336 | 17 | 266 | 4070 (93.87%) |

## Riesgos y limitaciones detectadas

- **MEDIUM · pseudo_label_target**: El target es una pseudoetiqueta derivada de reglas; una métrica casi perfecta no demuestra por sí sola una mejora real de QoE.
- **HIGH · duplicate_feature_vectors**: Varias ventanas contienen entradas idénticas; las métricas deben reportarse por sesión y los splits deben permanecer agrupados.
- **HIGH · high_window_overlap**: La mayoría de las ventanas adyacentes se solapan; su cantidad no representa observaciones independientes.
- **HIGH · cross_split_feature_overlap**: Existen vectores idénticos entre splits aunque las sesiones estén separadas.
- **HIGH · class_imbalance**: La clase minoritaria representa menos del 15% de las ventanas; deben usarse métricas por clase y balanceadas.
- **MEDIUM · constant_features**: Estas variables son constantes y no discriminan en el dataset actual: lookback_duration_seconds, measurements_count.

## Solapamiento predictivo

- Ventanas adyacentes solapadas: 4319 de 4319 (100.00%).
- Sesiones con una sola clase: 17 de 17.
- Los splits son por sesión; el solapamiento de vectores entre splits se reporta como limitación, no se oculta.

## Interpretación

Las métricas oficiales deben presentarse junto al baseline, las métricas balanceadas y estas limitaciones. La validación definitiva del objetivo requiere más sesiones móviles independientes y una comparación de QoE bajo degradaciones reales.
