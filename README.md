# Streaming Adaptativo mediante Machine Learning

## 1. Integrantes
- Alexis Guamán
- Cinthya Ramón

## 2. Descripción general
El proyecto busca mantener la continuidad y calidad de una transmisión cuando la conexión de red cambia. Durante una transmisión puede presentarse una reducción de ancho de banda, aumento de latencia, fluctuaciones, pérdida de paquetes, caídas de bitrate, frames omitidos, desconexiones o incluso la pérdida completa de la señal. Una configuración fija puede fallar cuando la red cambia, por lo que es necesario un mecanismo de adaptación.

## 3. Problema
Durante una transmisión, la calidad seleccionada puede superar la capacidad real de la red. Cuando esto ocurre pueden aparecer congelamientos, retrasos, cortes, pérdida de audio, reconexiones o interrupción completa. 

Una reducción manual puede llegar tarde. Por ello se propone utilizar modelos de Machine Learning que analicen las condiciones actuales y el historial reciente para tomar decisiones proactivas.

## 4. Propuesta
El sistema tendrá dos modelos operando en conjunto:

### Modelo reactivo
Analiza el estado actual de la red de manera instantánea.
Entrada final:
- upload_mbps
- download_mbps
- latency_ms

Salida:
- low
- medium
- high

### Modelo predictivo
Analiza una ventana temporal de 120 segundos buscando detectar patrones de degradación antes de que el evento afecte críticamente la transmisión.
Salida:
- maintain
- downgrade_needed

El modelo predictivo intenta anticipar una degradación antes de que ocurra.

## 5. Funcionamiento conceptual

```text
Métricas actuales
    ↓
Modelo reactivo
    ↓
Perfil recomendado

Historial de 120 segundos
    ↓
Modelo predictivo
    ↓
Riesgo de reducción

Ambos resultados
    ↓
Futuro agente de decisiones
```
*Aclaración:* El agente automático todavía no está implementado.

## 6. Alcance de la Fase 1
La Fase 1 incluye:
- búsqueda de datasets
- preparación de datos
- creación de pseudoetiquetas
- ventanas temporales
- entrenamiento
- evaluación
- validación por sesiones
- selección de modelos
- congelación de artefactos
- pruebas de recarga
- reproducibilidad

La Fase 1 no incluye:
- OBS
- VDO.Ninja
- RTMP
- MediaMTX
- FFmpeg
- transmisión real
- cambios automáticos
- fallback real

## 7. Datasets
Para el modelo reactivo se utiliza un dataset público de mediciones de red que contiene velocidad de subida, velocidad de descarga y latencia.
Para el modelo predictivo se agrupan sesiones temporales de throughput utilizando ventanas de observación para capturar tendencias y predecir degradaciones futuras.
**Limitaciones:** La utilización de datos públicos y estáticos implica que el entorno de entrenamiento carece de la telemetría específica que producirán las herramientas de video localmente.

## 8. Preparación de datos
- limpieza y normalización de nombres
- conversión de unidades
- tratamiento de valores nulos
- eliminación de columnas incompatibles con un entorno puramente local
- separación train, validation y test
- división por sesiones (para evitar fuga temporal)
- creación de características temporales basadas en ventanas de 120 segundos

## 9. Pseudoetiquetas reactivas
La etiqueta `recommended_profile` no es obtenida de una transmisión real. Se generó mediante reglas de capacidad.

| Perfil | Bitrate | Capacidad mínima |
|---|---:|---:|
| low | 1000 kbps | 1.35 Mbps |
| medium | 2500 kbps | 3.375 Mbps |
| high | 5000 kbps | 6.75 Mbps |

El alto rendimiento del modelo reactivo significa que aprendió la heurística. No significa que esté validado en producción.

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

## 13. Modelos finales
**Modelo reactivo final:**
- Modelo: DecisionTreeClassifier
- Variables: upload_mbps, download_mbps, latency_ms
- Macro F1 test: 0.9977

**Modelo predictivo final:**
- Modelo: RandomForestClassifier
- Umbral: 0.55
- Macro F1 validación agrupada: 0.5952
- Mejor baseline (Validación): 0.4799
- Macro F1 test: 0.4950
- Recall downgrade_needed (Test): 0.3333
- Falsos positivos: 21
- Falsos negativos: 4

## 14. Generalization gap
El generalization_gap se calcula como la diferencia entre la media de validación agrupada y la métrica de test en conjuntos aislados:
`generalization_gap = validation_cv_macro_f1_mean - test_macro_f1`
`0.5952 - 0.4950 = 0.1002`

Clasificación: **attention**
El modelo mejoró frente a la primera versión tras aplicar mitigaciones de fuga de datos, pero todavía presenta variabilidad e inestabilidad entre sesiones invisibles.

## 15. Interpretación de resultados
- El modelo reactivo reproduce casi a la perfección la heurística introducida originalmente.
- El modelo predictivo supera al baseline estadístico de forma clara en validación cruzada.
- Sin embargo, el predictivo tiene un desempeño moderado en test.
- El recall para eventos de degradación es limitado. Todavía puede omitir degradaciones y generar falsas alarmas.
- Por ende, no debe controlar automáticamente una transmisión bajo el estado actual.

## 16. Estructura del repositorio
```
Adaptive-Streaming-ai/
├── config/
│   └── model_input_contract_v2.json
├── data/
│   └── processed/
│       ├── dataset_reactivo.csv
│       ├── dataset_predictivo.csv
│       ├── dataset_metadata.json
│       └── data_dictionary.csv
├── models/
│   ├── phase1_final_release/
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
│   ├── reporte_final_fase1.md
│   └── limpieza_documental_final.md
├── scripts/
│   └── verify_phase1_release.py
├── src/
│   └── feature_builder_v2.py
├── tests/
│   └── test_phase1_final_release.py
├── AGENTS.md
├── README.md
├── requirements.txt
└── .gitignore
```

## 17. Instalación
```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 18. Ejecución
Para reproducir la pipeline de experimentación:
1. Abrir `notebooks/01_carga_preparacion_dataset.ipynb`
2. Abrir `notebooks/02_entrenamiento_modelos.ipynb`
3. Abrir `notebooks/03_prediccion_nuevos_ejemplos.ipynb`

Ejemplo para iniciar el entorno de desarrollo:
```bash
jupyter notebook
```

## 19. Verificación de la versión final
Comprobación de la integridad del release Phase 1:
```bash
python scripts/verify_phase1_release.py
```
*(Comprueba la existencia del manifiesto, valida los hashes, verifica firmas de entrada y asegura inferencias reproducibles sin fugas).*

Para pruebas automatizadas:
```bash
pytest tests/test_phase1_final_release.py -v
```
*(Valida invariantes técnicos definidos mediante fixtures de unit testing).*

## 20. Artefactos finales
Los recursos estáticos certificados de la Fase 1 se encuentran aislados en `models/phase1_final_release/`.
Este directorio incluye:
- modelos
- preprocesadores
- artefactos
- metadatos
- contrato
- manifiesto
- hashes

## 21. Estados actuales
- `phase1_models_ready = true`: Los modelos cumplen todos los estándares técnicos y científicos de la fase offline.
- `ready_for_phase2_data_collection = true`: El esquema de variables locales permite avanzar a la Fase 2 y comenzar a grabar datos.
- `ready_for_shadow_mode = false`: Aún no se ha orquestado el bucle de datos real para evaluar el impacto en vivo.
- `ready_for_automatic_control = false`: El sistema no posee autoridad para inyectar decisiones automáticas al hardware/software.
- `production_ready = false`: Todo el proyecto se considera en fase alfa de investigación.

## 22. Limitaciones
- Uso extensivo de datasets públicos con features limitados.
- Dependencia directa de pseudoetiquetas.
- Dependencia de throughput como proxy ante la falta temporal de métricas audiovisuales locales (FPS, dropped frames).
- Pocas degradaciones presentes en el set de datos.
- Fuertes diferencias estadísticas entre sesiones.
- Recall muy bajo para predicción adelantada (`downgrade_needed`).
- Ausencia de telemetría real.
- Ausencia de integración con OBS, VDO.Ninja.
- Ausencia de control automático (solo predicción sin impacto real).
- Ausencia de un mecanismo de fallback robusto implementado.
- El repositorio no está listo para producción.

## 23. Fase 2
La siguiente etapa del proyecto construirá y evaluará la arquitectura en un flujo vivo.
Esto incluirá:
- diseño de arquitectura
- VDO.Ninja
- OBS
- OBS WebSocket
- RTMP
- MediaMTX
- FFmpeg
- telemetría real
- almacenamiento por sesiones
- ejecución de modelos en modo lectura
- etiquetado de degradaciones
- reentrenamiento futuro

El control automático no será el primer paso de esta nueva fase. Se primará la recolección masiva de eventos.

## 24. Advertencia final
> [!WARNING]
> Este proyecto es un prototipo académico. Los modelos actuales no deben utilizarse para controlar automáticamente transmisiones reales ni para tomar decisiones críticas de producción.
