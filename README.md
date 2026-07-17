# StreamML

**Streaming Adaptativo y Prediccion de Reduccion de Calidad mediante Machine Learning**

**Integrantes:** Alexis Guaman y Cinthya Ramon.

StreamML es una entrega reproducible de Machine Learning offline orientada a dos decisiones relacionadas con la calidad de una transmision: recomendar un perfil segun las condiciones actuales y anticipar si el perfil observado deberia mantenerse o reducirse. El repositorio incluye preparacion de datos, entrenamiento, evaluacion, inferencia, notebooks documentados, pruebas automatizadas y una interfaz Streamlit.

La publicacion actual no controla una transmision real. VDO.Ninja, OBS Studio, RTMP, MediaMTX, FFmpeg, telemetria en vivo, agente autonomo y video de respaldo pertenecen a la arquitectura prevista, pero no tienen una implementacion activa en este arbol.

## Objetivos de Machine Learning

### Modelo reactivo

Clasifica una medicion actual en uno de tres perfiles:

- `low`
- `medium`
- `high`

Utiliza exactamente estas variables:

| Variable | Unidad | Significado |
|---|---|---|
| `upload_mbps` | Mbps | Velocidad actual de subida |
| `download_mbps` | Mbps | Velocidad actual de descarga |
| `latency_ms` | ms | Latencia actual |

El target es una pseudoetiqueta construida con umbrales de capacidad y penalizaciones por latencia. Su definicion completa se conserva en `config/reactive_feature_contract.json`.

### Modelo predictivo

Clasifica una ventana temporal en una de dos clases:

- `maintain`: las condiciones permiten mantener el perfil actual.
- `downgrade_needed`: el horizonte posterior contiene evidencia para reducirlo.

El contrato utiliza 19 estadisticas calculadas exclusivamente sobre **120 segundos historicos** y una etiqueta calculada en los **30 segundos estrictamente posteriores**. Entre las variables se encuentran media, mediana, minimos, maximos, percentiles, dispersion, pendiente, cambio de throughput, proporciones bajo capacidades requeridas y perfil actual.

El modelo no recibe columnas futuras ni el target como entrada. La lista y el orden exactos se encuentran en `config/predictive_feature_contract.json`.

## Metodologia

El flujo aplica las siguientes reglas:

1. Se utilizan datos publicos y no se generan observaciones sinteticas.
2. Las variables de entrada se obtienen de contratos versionados.
3. Las sesiones completas se mantienen separadas entre train, validacion y test.
4. La busqueda de hiperparametros se realiza dentro de entrenamiento con grupos de sesiones.
5. El algoritmo y el threshold predictivo se seleccionan con validacion.
6. Test se utiliza unicamente para estimar generalizacion final.
7. Se comparan los modelos contra `DummyClassifier(strategy='most_frequent')`.
8. Se reportan accuracy, balanced accuracy, Macro F1, recall, F1 por clase y matrices de confusion.
9. Los modelos se publican junto con contratos, metricas, procedencia, versiones y hashes.

Macro F1 y balanced accuracy son especialmente importantes porque el dataset predictivo esta desbalanceado. Una accuracy elevada por si sola no demostraria que el modelo reconoce correctamente ambas clases.

## Datos oficiales

| Dataset | Filas | Sesiones | Variables del modelo | Target |
|---|---:|---:|---:|---|
| `data/processed/reactive_dataset.csv` | 26,686 | 26,686 | 3 | `low`, `medium`, `high` |
| `data/processed/predictive_dataset.csv` | 3,306 | 120 | 19 | `maintain`, `downgrade_needed` |

La procedencia, licencia, URLs y hashes conocidos se documentan en `data/raw/source_manifest.json`. El archivo bruto reactivo y su licencia se conservan localmente; los CSV y ZIP grandes estan excluidos de Git. La fuente predictiva bruta no esta fisicamente incluida en el checkout actual, por lo que `scripts/prepare_datasets.py` requiere restaurarla antes de reconstruir completamente ese dataset.

`data/interim/` esta reservado para esquemas, estadisticas y transformaciones generadas durante la preparacion. `data/processed/` contiene unicamente los dos datasets finales de entrenamiento.

## Resultados reales

| Modelo | Algoritmo seleccionado | Validacion Macro F1 | Test Macro F1 | Test balanced accuracy | Baseline test Macro F1 |
|---|---|---:|---:|---:|---:|
| Reactivo | `DecisionTreeClassifier` | 100.00% | 99.91% | 99.83% | 30.17% |
| Predictivo | `RandomForestClassifier` | 99.06% | 93.25% | 95.68% | 47.99% |

El modelo predictivo utiliza un threshold de `0.50`, elegido con validacion. En test obtuvo 53 aciertos y 4 errores para `maintain`, ademas de 671 aciertos y 11 errores para `downgrade_needed`. Las cifras completas se generan mediante Python y se almacenan en los `metrics.json` de cada modelo.

## Modelos publicados

```text
models/release/
├── release_manifest.json
├── reactive/
│   ├── model.joblib
│   ├── feature_contract.json
│   ├── class_mapping.json
│   ├── metrics.json
│   ├── training_manifest.json
│   ├── source_manifest.json
│   └── requirements_snapshot.txt
└── predictive/
    ├── model.joblib
    ├── feature_contract.json
    ├── class_mapping.json
    ├── metrics.json
    ├── threshold.json
    ├── training_manifest.json
    ├── source_manifest.json
    └── requirements_snapshot.txt
```

Los JSON no son modelos duplicados. Cada uno conserva una responsabilidad: orden de variables, clases, metricas, procedimiento de entrenamiento, procedencia o threshold. Las copias junto al modelo hacen que cada publicacion sea autocontenida y verificable mediante los hashes de `release_manifest.json`.

## Notebooks oficiales

El proyecto mantiene exactamente tres notebooks, todos ejecutados desde kernels nuevos y sin errores:

### `01_data_preparation.ipynb`

- Revisa procedencia y licencia.
- Carga y audita ambos datasets.
- Normaliza tipos y elimina registros incompatibles.
- Analiza variables y distribuciones de clases.
- Valida contratos, targets y columnas prohibidas.
- Comprueba particiones disjuntas por `session_id`.
- Audita una ventana temporal real y la ausencia de fuga futura.
- Guarda y vuelve a cargar los CSV finales.

### `02_model_training.ipynb`

- Carga datasets y contratos preparados.
- Ejecuta el entrenamiento mediante scripts reproducibles.
- Compara baseline, regresion logistica, arbol y random forest.
- Selecciona modelos y threshold con validacion.
- Presenta accuracy, balanced accuracy, Macro F1, recall y F1 por clase.
- Genera matrices de confusion e importancia de variables.
- Compara la mejora real frente al baseline.
- Comprueba todos los artefactos publicados.

### `03_model_inference.ipynb`

- Carga los dos modelos oficiales sin reentrenarlos.
- Verifica nombres y orden de variables.
- Ejecuta ejemplos reactivos reales para `low`, `medium` y `high`.
- Ejecuta ejemplos predictivos reales para ambas clases disponibles.
- Muestra probabilidades, threshold, target, prediccion y acierto.
- Explica como interpretar cada salida y sus limitaciones.

Para ejecutarlos desde cero y en orden:

```powershell
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 notebooks/01_data_preparation.ipynb
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 notebooks/02_model_training.ipynb
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 notebooks/03_model_inference.ipynb
```

## Interfaz Streamlit

La aplicacion ofrece cinco vistas:

1. Inicio.
2. Modelo reactivo.
3. Modelo predictivo.
4. Prediccion mediante CSV.
5. Resultados y metricas.

La GUI carga exclusivamente:

- `models/release/reactive/model.joblib`
- `models/release/predictive/model.joblib`

Los contratos y el threshold se leen de los artefactos oficiales. Si un CSV no contiene las columnas requeridas, la aplicacion informa cuales faltan y no ejecuta una prediccion incompatible.

```powershell
streamlit run app.py
```

## Estructura del repositorio

```text
config/             configuracion del dataset y contratos de entrada
data/raw/           manifiesto, licencia y fuentes locales ignoradas por Git
data/interim/       transformaciones y metadatos regenerables
data/processed/     datasets finales de entrenamiento
models/release/     modelos oficiales y artefactos verificables
notebooks/          preparacion, entrenamiento e inferencia documentados
reports/            fichas de los datasets
scripts/            comandos reproducibles del flujo
src/                implementacion reutilizable de datos y modelos
tests/              pruebas de contratos, splits, etiquetas y publicacion
app.py              interfaz Streamlit
```

## Instalacion

Se recomienda Python 3.11. En Windows:

```powershell
py -3.11 -m venv .venv311
.venv311\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Los entornos virtuales, secretos, caches, ZIP y CSV brutos grandes estan excluidos mediante `.gitignore`.

## Flujo reproducible

```powershell
# Requiere que todas las fuentes brutas declaradas esten disponibles localmente.
python scripts\prepare_datasets.py

# Entrena los dos modelos y publica sus artefactos.
python scripts\train_models.py

# Recalcula la evaluacion final y actualiza el manifiesto de publicacion.
python scripts\evaluate_models.py

# Ejecuta un ejemplo reproducible de cada modelo.
python scripts\demo_models.py

# Verifica archivos, hashes, contratos, modelos y metricas.
python scripts\verify_release.py

# Ejecuta todas las pruebas.
pytest -v
```

El entrenamiento utiliza `random_state = 42`. Los scripts fallan de forma explicita si falta una fuente, contrato, columna o artefacto obligatorio.

## Verificacion actual

La ultima ejecucion completa produjo:

- Notebook de preparacion: 9/9 celdas de codigo, sin errores.
- Notebook de entrenamiento: 9/9 celdas de codigo, sin errores.
- Notebook de inferencia: 8/8 celdas de codigo, sin errores.
- Pruebas automatizadas: `24 passed`.
- Verificador: `STREAMML RELEASE VERIFIED`.
- `git diff --check`: sin errores de whitespace.

## Limitaciones

Los artefactos actuales no soportan:

- Predicciones a 5, 10, 20 o 30 minutos.
- Jitter o perdida de paquetes como entradas.
- Clase predictiva `critical`.
- Control directo de OBS o FFmpeg.
- Decisiones de un agente autonomo.
- Histeresis, tiempo minimo entre cambios o video de respaldo.

Estas capacidades requieren datos operativos reales, nuevos contratos, nuevas etiquetas, reentrenamiento y pruebas de integracion. No se simulan mediante reglas manuales porque eso produciria resultados que no pertenecen a los modelos publicados.

## Seguridad

`.env` permanece excluido de Git. `.env.example` contiene solo nombres y valores neutros para una posible integracion futura con OBS WebSocket. Las credenciales reales nunca deben almacenarse en notebooks, codigo, documentacion o commits. Si una clave fue compartida, debe rotarse antes de publicar el repositorio.
