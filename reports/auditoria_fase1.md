# Auditoría Fase 1
**Fecha:** 2026-07-13 22:20:47

## Notebooks Ejecutados
- 01_carga_preparacion_dataset.ipynb: Exitoso
- 02_entrenamiento_modelos.ipynb: Exitoso
- 03_prediccion_nuevos_ejemplos.ipynb: Exitoso

## Archivos Generados Confirmados
- dataset_reactivo.csv
- dataset_predictivo.csv
- data_dictionary.csv
- dataset_metadata.json
- modelo_reactivo.joblib
- modelo_predictivo.joblib
- model_metadata.json
- reports/agent_simulation_results.csv

## Modelos Seleccionados y Métricas de Test
- Reactivo: RandomForest (F1: 0.994632)
- Predictivo: GradientBoosting (F1: 0.733871)

## Comparación contra Baselines

MODELO REACTIVO

| Métrica | Baseline | Modelo | Diferencia |
|---|---:|---:|---:|
| Accuracy | 0.831084 | 0.998501 | 0.167416 |
| Balanced Accuracy | 0.333333 | 0.993897 | 0.660564 |
| Macro Precision | 0.277028 | 0.995372 | 0.718343 |
| Macro Recall | 0.333333 | 0.993897 | 0.660564 |
| Macro F1 | 0.302584 | 0.994632 | 0.692048 |

**Recalls por clase:** low: 0.992443, medium: 0.989247, high: 1.000000
**Matriz de confusión:** [[3326, 0, 0], [0, 394, 3], [2, 1, 276]]


MODELO PREDICTIVO

| Métrica | Mejor baseline | Modelo | Diferencia |
|---|---:|---:|---:|
| Accuracy | 0.818182 | 0.939394 | 0.121212 |
| Balanced Accuracy | 0.591398 | 0.733871 | 0.142473 |
| Macro Precision | 0.538404 | 0.733871 | 0.195467 |
| Macro Recall | 0.591398 | 0.733871 | 0.142473 |
| Macro F1 | 0.539773 | 0.733871 | 0.194098 |

**Recalls por clase:** maintain: 0.967742, downgrade_needed: 0.500000
**Falsos Positivos:** 3 | **Falsos Negativos:** 3
**Umbral Utilizado:** 0.450000
**Matriz de confusión:** [[90, 3], [3, 3]]

## Validaciones Críticas
- **Comprobación de fuga:** Verificado: Sin fuga (split test aislado)
- **Comprobación de recarga:** Verificado: Modelos cargan sin reentrenar
- **Comprobación de inferencia:** Verificado: Agente genera predicciones estables
- **Errores encontrados y corregidos:** Se corrigió la duplicación de la métrica Macro_F1 del predictivo en las claves del modelo reactivo y se calcularon correctamente todas las métricas en test.
- **Limitaciones:** Los datos son estáticos provenientes de benchmarks públicos. La mejora del modelo reactivo sobre el baseline es 0.692048; el modelo ha aprendido pseudoetiquetas basadas en heurísticas, por lo que su evaluación actual no demuestra rendimiento real en entornos ruidosos.

## Estados Finales
- `phase1_ready`: True
- `production_ready`: False
