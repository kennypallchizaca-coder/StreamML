# Streaming Adaptativo mediante Machine Learning

**Integrantes:** Alexis Guamán y Cinthya Ramón

## Descripción del problema
Las transmisiones en vivo IRL sufren caídas de calidad debido a fluctuaciones en la red móvil. Los sistemas reaccionan tardíamente provocando cortes. Se propone desarrollar un sistema autónomo de streaming adaptativo mediante Machine Learning.

## Datasets
- **Reactivo:** RTR-NetzTest Open Data.
- **Predictivo:** Ghent 4G/LTE Bandwidth Logs. (Ghent usa descarga como proxy temporal).
(Los datos todavía no provienen de OBS/VDO.Ninja).

## Arquitectura de Modelos
- **Modelo Reactivo:** Predecir estado actual. Aprende pseudoetiquetas basadas en capacidad y perfil.
- **Modelo Predictivo:** Predecir tendencia futura y anticipar caídas.

## Estructura del proyecto
```text
Adaptive-Streaming-ai/
├── config/
├── data/
├── docs/
├── models/
├── notebooks/
├── reports/
└── src/
```

## Requisitos e Instalación
1. Crear entorno: `python -m venv venv`
2. Activar entorno e instalar requerimientos: `pip install -r requirements.txt`

## Orden de ejecución de notebooks
1. `notebooks/01_carga_preparacion_dataset.ipynb`
2. `notebooks/02_entrenamiento_modelos.ipynb`
3. `notebooks/03_prediccion_nuevos_ejemplos.ipynb`

## Modelos Seleccionados y Métricas Reales

### Modelo Reactivo
- **Algoritmo:** RandomForest
- **Macro F1 de test:** 0.994632
- **Baseline Macro F1:** 0.302584

### Modelo Predictivo
- **Algoritmo:** GradientBoosting
- **Macro F1 de test:** 0.733871
- **Mejor baseline Macro F1:** 0.539773
- **Recall de downgrade_needed:** 0.500000
- **Falsos positivos:** 3
- **Falsos negativos:** 3
- **Umbral:** 0.450000

## Limitaciones
- El modelo reactivo aprende pseudoetiquetas.
- Ghent usa descarga como proxy temporal para predecir subida.
- Los datos todavía no provienen de OBS/VDO.Ninja.

## Próximos pasos
Integración en tiempo real con OBS Studio y VDO.Ninja mediante WebSockets para recopilación e inferencia dinámica.

## Estado de la Fase 1
- `phase1_ready`: True (para el prototipo académico)
- `production_ready`: False

**Advertencia:** El sistema no está listo para producción.
