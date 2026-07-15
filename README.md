# Streaming Adaptativo mediante Machine Learning

## 1. Integrantes
- **Alexis Guamán**
- **Cinthya Ramón**

## 2. Descripción general
Sistema de Machine Learning que analiza las condiciones de red en tiempo real para recomendar el perfil de calidad óptimo durante una transmisión de video en vivo. El proyecto aborda las transmisiones IRL (In Real Life) en entornos urbanos con geografía compleja, donde las fluctuaciones de red hacen inviable una configuración fija de bitrate.

## 3. Estado actual del proyecto

| Componente | Estado |
|---|---|
| Modelo reactivo (DecisionTree) | ✅ Entrenado y congelado |
| Modelo predictivo (RandomForest) | ✅ Entrenado y congelado |
| Integración OBS Studio | ✅ Funcionando |
| Servidor MediaMTX | ✅ Funcionando |
| Recolección de telemetría real | ✅ Funcionando |
| Etiquetado de sesiones | ✅ Funcionando |
| Inferencia con datos reales | ⏳ Pendiente (Fase 2) |
| Control automático de OBS | 🔒 Desactivado |
| Producción | ❌ No disponible |

> [!WARNING]
> Este proyecto es un prototipo académico. Los modelos actuales no deben utilizarse para controlar automáticamente transmisiones reales ni para tomar decisiones críticas de producción.

## 4. Problema
Durante una transmisión, la calidad seleccionada puede superar la capacidad real de la red. Cuando esto ocurre pueden aparecer congelamientos, retrasos, cortes, pérdida de audio, reconexiones o interrupción completa.

Una reducción manual puede llegar tarde. Por ello se propone utilizar modelos de Machine Learning que analicen las condiciones actuales y el historial reciente para tomar decisiones proactivas.

## 5. Arquitectura

```text
VDO.Ninja (Cámara móvil)
    ↓ WebRTC
OBS Studio (Composición y codificación)
    ↓ RTMP
MediaMTX (Servidor de restreaming)
    ↓
Telemetría en tiempo real → Modelos ML (Shadow Mode)
```

### Modelo reactivo
Analiza el estado actual de la red de manera instantánea.

Entrada:
- `upload_mbps`, `download_mbps`, `latency_ms`

Salida:
- `low`, `medium`, `high`

### Modelo predictivo
Analiza una ventana temporal de 120 segundos buscando detectar patrones de degradación antes de que el evento afecte críticamente la transmisión.

Salida:
- `maintain`, `downgrade_needed`

> **Nota importante:** Durante la recolección de telemetría actual, los modelos de ML permanecen desactivados. El bitrate reportado por OBS no se utiliza como indicador de capacidad de red disponible.

## 6. Resultados de la Fase 1

### Modelo reactivo final
- Algoritmo: `DecisionTreeClassifier`
- Variables: `upload_mbps`, `download_mbps`, `latency_ms`
- Macro F1 test: **0.9977**

### Modelo predictivo final
- Algoritmo: `RandomForestClassifier`
- Umbral: 0.55
- Macro F1 validación agrupada: **0.5952**
- Mejor baseline: 0.4799
- Macro F1 test: **0.4950**
- Recall downgrade_needed (test): 0.3333
- Falsos positivos: 21
- Falsos negativos: 4
- Generalization gap: **0.1002** (attention)

### Pseudoetiquetas reactivas

| Perfil | Bitrate | Capacidad mínima |
|---|---:|---:|
| low | 1000 kbps | 1.35 Mbps |
| medium | 2500 kbps | 3.375 Mbps |
| high | 5000 kbps | 6.75 Mbps |

El alto rendimiento del modelo reactivo significa que aprendió la heurística. No significa que esté validado en producción.

## 7. Avance de la Fase 2

### Recolección de telemetría real
Se ha implementado un sistema completo de recolección que captura métricas segundo a segundo desde OBS Studio, la red del sistema y MediaMTX.

### Primera sesión estable validada
Se ejecutó una sesión de recolección de 60 segundos en condiciones estables:
- **60 muestras** registradas
- `invalid_rows = 0`
- `timestamp_errors = 0`
- `validation_status = valid`
- Sin frames omitidos
- Sin acciones automáticas aplicadas (`action_applied = none`)
- `models_executed = false` (modelos desactivados durante recolección)

## 8. Datasets
Para el modelo reactivo se utiliza un dataset público de mediciones de red que contiene velocidad de subida, velocidad de descarga y latencia.
Para el modelo predictivo se agrupan sesiones temporales de throughput utilizando ventanas de observación para capturar tendencias y predecir degradaciones futuras.

**Fuentes:**
- Reactivo: [RTR-NetzTest Open Data](https://www.netztest.at/en/Opendata)
- Predictivo: [Ghent University 4G/LTE Dataset](http://users.ugent.be/~jvdrhoof/dataset-4g/)

**Limitaciones:** La utilización de datos públicos y estáticos implica que el entorno de entrenamiento carece de la telemetría específica que producirán las herramientas de video localmente.

## 9. Preparación de datos
- Limpieza y normalización de nombres
- Conversión de unidades
- Tratamiento de valores nulos
- Eliminación de columnas incompatibles con un entorno puramente local
- Separación train, validation y test
- División por sesiones (para evitar fuga temporal)
- Creación de características temporales basadas en ventanas de 120 segundos

## 10. Características del modelo predictivo
- `throughput_mean`: Promedio de velocidad en la ventana.
- `throughput_median`: Mediana para robustez ante picos.
- `throughput_min`, `throughput_max`: Rango de la conexión.
- `throughput_std`, `throughput_coefficient_variation`: Medidas de inestabilidad de la red.
- `throughput_p10`, `throughput_p25`: Cuantiles de caídas críticas.
- `throughput_first`, `throughput_last`: Valores en los extremos de la ventana temporal.
- `throughput_change`, `throughput_slope`: Evolución y tendencia temporal de la capacidad.
- `measurements_count`, `lookback_duration_seconds`: Metadatos de la propia ventana temporal (para asegurar suficiencia de datos).
- `proportion_below_low`, `proportion_below_medium`, `proportion_below_high`: Porcentaje de tiempo que la red pasa por debajo del umbral de seguridad de cada perfil.
- `current_profile`: El perfil actual asignado a la transmisión.
- `required_capacity_mbps`: La capacidad teórica necesaria que exige el perfil actual.

## 11. Modelos evaluados
**Modelos reactivos evaluados:** DummyClassifier, LogisticRegression, DecisionTree, RandomForest, GradientBoosting.
**Modelos predictivos evaluados:** LogisticRegression, DecisionTree, RandomForest, GradientBoosting, HistGradientBoosting.

## 12. Validación agrupada
Para asegurar que el modelo sea generalizable, no se utilizó una división aleatoria por filas.
Se implementó `GroupKFold` agrupando por `session_id`, validando sobre 27 sesiones a través de 5 folds. Esto evita que las ventanas temporales superpuestas de una misma sesión aparezcan simultáneamente en entrenamiento y validación (Data Leakage).

## 13. Generalization gap
El generalization_gap se calcula como la diferencia entre la media de validación agrupada y la métrica de test en conjuntos aislados:
`generalization_gap = validation_cv_macro_f1_mean - test_macro_f1`
`0.5952 - 0.4950 = 0.1002`

Clasificación: **attention**
El modelo mejoró frente a la primera versión tras aplicar mitigaciones de fuga de datos, pero todavía presenta variabilidad e inestabilidad entre sesiones invisibles.

## 14. Interpretación de resultados
- El modelo reactivo logra una alta precisión al reproducir la heurística introducida originalmente.
- El modelo predictivo supera al baseline estadístico de forma clara en validación cruzada.
- Sin embargo, el predictivo tiene un desempeño moderado en test.
- El recall para eventos de degradación es limitado. Todavía puede omitir degradaciones y generar falsas alarmas.
- Por ende, no debe controlar automáticamente una transmisión bajo el estado actual.

## 15. Estructura del repositorio
```
StreamML — Streaming Adaptativo mediante Machine Learning/
├── config/
│   ├── model_input_contract_v2.json
│   ├── data_collection_config.json
│   ├── shadow_agent_config.json
│   └── telemetry_schema.json
├── data/
│   ├── processed/
│   │   ├── dataset_reactivo.csv
│   │   ├── dataset_predictivo.csv
│   │   ├── dataset_metadata.json
│   │   └── data_dictionary.csv
│   └── telemetry/
│       ├── example_telemetry.csv
│       ├── telemetry_schema.json
│       └── .gitignore
├── docs/
│   ├── arquitectura_fase2.md
│   ├── auditoria_paridad_features.md
│   ├── guia_demostracion.md
│   ├── protocolo_recoleccion_fase2.md
│   ├── reporte_avance_fase2.md
│   └── validacion_shadow_mode.md
├── models/
│   ├── phase1_final_release/
│   │   ├── manifest.json
│   │   ├── model_input_contract_v2.json
│   │   ├── model_metadata_phase1_final.json
│   │   ├── modelo_reactivo_phase1_final.joblib
│   │   ├── modelo_predictivo_phase1_final.joblib
│   │   ├── preprocesador_reactivo_phase1_final.joblib
│   │   └── preprocesador_predictivo_phase1_final.joblib
│   ├── modelo_reactivo_phase1_final.joblib
│   ├── modelo_predictivo_phase1_final.joblib
│   ├── preprocesador_reactivo_phase1_final.joblib
│   ├── preprocesador_predictivo_phase1_final.joblib
│   └── model_metadata_phase1_final.json
├── notebooks/
│   ├── 01_carga_preparacion_dataset.ipynb
│   ├── 02_entrenamiento_modelos.ipynb
│   └── 03_prediccion_nuevos_ejemplos.ipynb
├── reports/
│   └── figures/
│       ├── ghent_sample_sessions.png
│       ├── ghent_session_duration.png
│       ├── ghent_throughput_dist.png
│       └── reactivo_target_dist.png
├── scripts/
│   ├── audit_shadow.py
│   ├── check_presentation_ready.py
│   ├── label_session.py
│   ├── run_data_collection_session.py
│   ├── run_shadow_agent.py
│   ├── run_shadow_runtime.py
│   ├── run_telemetry_collector.py
│   ├── test_obs_connection.py
│   └── verify_phase1_release.py
├── src/
│   ├── feature_builder_v2.py
│   ├── obs_telemetry_collector.py
│   ├── session_data_collector.py
│   ├── shadow_agent.py
│   ├── telemetry_buffer.py
│   └── telemetry_collector.py
├── tests/
│   ├── test_label_session.py
│   ├── test_model_input_contract_v2.py
│   ├── test_obs_telemetry_collector.py
│   ├── test_phase1_final_release.py
│   ├── test_session_data_collector.py
│   ├── test_shadow_agent.py
│   ├── test_telemetry_buffer.py
│   └── test_telemetry_collector.py
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## 16. Demostración rápida

### Requisitos previos
- OBS Studio abierto con WebSocket habilitado
- VDO.Ninja transmitiendo hacia OBS
- MediaMTX ejecutándose

### Ejecutar sesión de recolección (30 segundos)
```bash
python scripts/run_data_collection_session.py --duration 30 --profile high --condition stable
```

### Verificar integridad del release
```bash
python scripts/verify_phase1_release.py
```

### Ejecutar pruebas automatizadas
```bash
pytest -v
```

### Verificar preparación para presentación
```bash
python scripts/check_presentation_ready.py
```

## 17. Instalación
```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 18. Limitaciones
- Uso extensivo de datasets públicos con features limitados.
- Dependencia directa de pseudoetiquetas.
- Dependencia de throughput como proxy ante la falta temporal de métricas audiovisuales locales (FPS, dropped frames).
- Pocas degradaciones presentes en el set de datos.
- Fuertes diferencias estadísticas entre sesiones.
- Recall muy bajo para predicción adelantada (`downgrade_needed`).
- El bitrate de OBS no se usa como capacidad disponible de la red.
- Los modelos no han sido validados con datos reales aún.
- Ausencia de control automático (solo predicción sin impacto real).
- Ausencia de un mecanismo de fallback robusto implementado.
- El repositorio no está listo para producción.

## 19. Advertencia final

> [!WARNING]
> Este proyecto es un prototipo académico. Los modelos actuales no deben utilizarse para controlar automáticamente transmisiones reales ni para tomar decisiones críticas de producción.
