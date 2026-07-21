# Reporte Final de Fase 1

## 1. Nombre del proyecto
Adaptive-Streaming-ai

## 2. Integrantes
- Alexis Guamán
- Cinthya Ramón

## 3. Fecha de cierre
2026-07-13

## 4. Problema investigado
Durante una transmisión de video en vivo (streaming), la calidad seleccionada por el usuario (resolución, bitrate) puede superar la capacidad de red real debido a fluctuaciones (ancho de banda, latencia, pérdida de paquetes). Esto ocasiona congelamientos, retrasos, cortes y reconexiones que degradan la experiencia.

## 5. Objetivo general
Diseñar e implementar un sistema inteligente que adapte de manera proactiva y reactiva la configuración de transmisión en función de las métricas de red, evitando degradaciones críticas en la experiencia del usuario.

## 6. Objetivos específicos
1. Determinar el perfil de red óptimo en tiempo real basado en métricas instantáneas (Reactivo).
2. Anticipar caídas en la capacidad de red analizando el comportamiento de los últimos 120 segundos (Predictivo).

## 7. Datasets utilizados
- **Reactivo:** dataset público de mediciones de red estáticas (`dataset_reactivo.csv`).
- **Predictivo:** dataset derivado agrupado en ventanas temporales (`dataset_predictivo.csv`).

## 8. Preparación de datos
Incluyó limpieza de anomalías, imputación de nulos, eliminación de columnas incompatibles con el entorno local (e.g. `network_type`, `cat_technology`, `signal_strength`, `transport_type`), agrupación por `session_id`, prevención de fuga temporal (Data Leakage) y creación de variables estadísticas temporales (medias, pendientes, cuantiles) sobre el throughput.

## 9. Variables del modelo reactivo
- `upload_mbps`
- `download_mbps`
- `latency_ms`

## 10. Variables del modelo predictivo
- `throughput_mean`
- `throughput_median`
- `throughput_min`
- `throughput_max`
- `throughput_std`
- `throughput_p10`
- `throughput_p25`
- `throughput_first`
- `throughput_last`
- `throughput_change`
- `throughput_slope`
- `throughput_coefficient_variation`
- `measurements_count`
- `lookback_duration_seconds`
- `proportion_below_low`
- `proportion_below_medium`
- `proportion_below_high`
- `current_profile`
- `required_capacity_mbps`

## 11. Pseudoetiquetas
- **Reactivo (`recommended_profile`):** Creadas heurísticamente usando el ancho de banda y la latencia actuales (low, medium, high).
- **Predictivo (`downgrade_needed`):** Binario (maintain, downgrade_needed). Indica si la capacidad futura caerá por debajo del perfil actual.

## 12. Ventanas temporales
Se analizó un historial de **120 segundos** para la extracción de características predictivas (estadísticas, tendencias y comportamiento histórico reciente).

## 13. División por sesiones
Para evitar fuga de datos (autocorrelación), se agruparon las secuencias por su identificador único `session_id`. Nunca una misma sesión participa simultáneamente en entrenamiento y evaluación.

## 14. Modelos evaluados
- **Reactivos:** DummyClassifier, LogisticRegression, DecisionTree, RandomForest, GradientBoosting.
- **Predictivos:** LogisticRegression, DecisionTree, RandomForest, GradientBoosting, HistGradientBoosting.

## 15. Baselines
El baseline seleccionado para validación fue `Dummy_Stratified` (Macro F1 = 0.4799).

## 16. Método GroupKFold
El modelo predictivo fue validado usando `GroupKFold` sobre `session_id`, lo que promedia el rendimiento sobre sesiones no vistas.

## 17. Número de sesiones
**27 sesiones** únicas.

## 18. Número de folds
**5 folds**.

## 19. Modelo reactivo seleccionado
**DecisionTreeClassifier** (Aprende perfectamente la regla heurística basada en 3 variables continuas).

## 20. Modelo predictivo seleccionado
**RandomForestClassifier**.

## 21. Umbral predictivo
**0.55**. Elegido para equilibrar F1 y Recall.

## 22. Métricas finales
- **Macro F1 Validación Predictivo:** 0.5952
- **Macro F1 Test Predictivo:** 0.4950

## 23. Matrices de confusión
- **Falsos positivos (Predictivo):** 21
- **Falsos negativos (Predictivo):** 4
- **Recall de downgrade_needed:** 0.3333

## 24. Generalization gap
Diferencia entre validación y test: `0.5952 - 0.4950 = 0.1002`. Clasificado como **attention**.

## 25. Sensibilidad
Comportamiento estable ante perturbaciones moderadas (desviación media de probabilidades de 0.0083 ante +5% de throughput).

## 26. Recarga
Superada. Los modelos y preprocesadores `_phase1_final.joblib` cargan sin error en un entorno limpio y en la verificación continua (`verify_phase1_release.py`).

## 27. Reproducibilidad
Superada. Las inferencias repetidas con los mismos datos entregan el mismo vector de probabilidades sin alterar los pesos del modelo de manera accidental.

## 28. Limitaciones
El modelo predictivo es entrenado usando variables proxy sobre datasets públicos estáticos y offline. Como resultado, su precisión en datos de test es moderada, genera falsas alarmas y tiene un bajo recall en predecir degradaciones reales. Falta probarlo con telemetría local de OBS y VDO.Ninja.

## 29. Archivos finales
Todos los artefactos congelados residen en `models/phase1_final_release/` (incluyendo su manifiesto verificable `manifest.json`).

## 30. Estado de cierre
La Fase 1 se cierra y se prohíbe optimizar hiperparámetros sobre datasets offline estáticos.
- `phase1_models_ready = true`
- `ready_for_phase2_data_collection = true`
- `ready_for_shadow_mode = false`
- `ready_for_automatic_control = false`
- `production_ready = false`
