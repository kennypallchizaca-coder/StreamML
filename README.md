# StreamML

**Streaming Adaptativo y Prediccion de Reduccion de Calidad mediante Machine Learning**

**Integrantes:** Alexis Guaman y Cinthya Ramon.

StreamML es un prototipo reproducible de streaming adaptativo. Mide la ruta de red, ejecuta dos modelos supervisados y utiliza un agente determinista para mantener, aumentar o reducir el perfil de OBS. Tambien cambia a una escena o archivo de respaldo cuando se pierde la señal y restaura el vivo tras un periodo estable.

La aplicacion integra React, FastAPI, WebSocket, un conector local de OBS, MediaMTX, FFmpeg y nginx. El codigo, los modelos y las pruebas automatizadas estan completos; antes de afirmar preparacion para produccion siguen siendo obligatorias pruebas fisicas con el telefono, OBS, credenciales reales de una plataforma y la red de despliegue.

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

El target es una pseudoetiqueta construida con umbrales de capacidad y penalizaciones por latencia. Su definicion completa se conserva en `src/streamml/config/reactive_feature_contract.json`.

### Modelo predictivo

Clasifica una ventana temporal en una de dos clases:

- `maintain`: las condiciones permiten mantener el perfil actual.
- `downgrade_needed`: el horizonte posterior contiene evidencia para reducirlo.

El contrato utiliza 19 estadisticas calculadas exclusivamente sobre **600 segundos historicos** y una etiqueta calculada en los **600 segundos estrictamente posteriores**. Entre las variables se encuentran media, mediana, minimos, maximos, percentiles, dispersion, pendiente, cambio de throughput, proporciones bajo capacidades requeridas y perfil actual.

El modelo no recibe columnas futuras ni el target como entrada. La lista y el orden exactos se encuentran en `src/streamml/config/predictive_feature_contract.json`.

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
| `data/processed/predictive_dataset.csv` | 4,336 | 17 | 19 | `maintain`, `downgrade_needed` |

La procedencia, licencia, URLs y hashes conocidos se documentan en `data/raw/source_manifest.json`. Los CSV y ZIP grandes estan excluidos de Git. `scripts/fetch_predictive_source.py` usa solicitudes HTTP Range para extraer del ZIP oficial solamente las 17 sesiones con al menos 20 minutos, sin descargar ni generar datos sinteticos.

`data/interim/` esta reservado para esquemas, estadisticas y transformaciones generadas durante la preparacion. `data/processed/` contiene unicamente los dos datasets finales de entrenamiento.

## Resultados reales

| Modelo | Algoritmo seleccionado | Validacion Macro F1 | Test Macro F1 | Test balanced accuracy | Baseline test Macro F1 |
|---|---|---:|---:|---:|---:|
| Reactivo | `DecisionTreeClassifier` | 100.00% | 99.91% | 99.83% | 30.17% |
| Predictivo | `LogisticRegression` | 100.00% | 100.00% | 100.00% | 48.91% |

El modelo predictivo utiliza un threshold de `0.50`, elegido con validacion. En test clasifico correctamente 42 ventanas `maintain` y 939 `downgrade_needed`. Este resultado perfecto debe interpretarse con cautela: solo existen 17 sesiones publicas suficientemente largas, las clases son muy desbalanceadas y cada sesion seleccionada contiene una sola clase. Las particiones permanecen separadas por sesion y contienen ambas clases, pero la validacion operativa con nuevas sesiones moviles sigue siendo necesaria.

## Modelos publicados

```text
models/registry/
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

## Aplicacion web online

La superficie comercial se encuentra en `apps/frontend/` y ofrece inicio de sesion, panel, creacion de transmision, monitoreo en vivo, historial, modelos y configuracion. La API de `apps/api/` persiste usuarios, sesiones, vinculaciones, telemetria, predicciones y auditoria con aislamiento por propietario.

El conector de `apps/connector/` se conecta a OBS WebSocket 5.x exclusivamente en loopback. Recoge estadisticas, mide por HTTP la ruta de subida/descarga hacia el servidor y consulta comandos autenticados y limitados a perfiles y escenas. El bitrate de OBS nunca se reutiliza como capacidad de red.

El agente aplica margen de capacidad, reducciones preventivas, cambios de un nivel, cinco confirmaciones antes de aumentar, cooldown de 30 segundos y temporizadores de perdida/recuperacion. El worker FFmpeg alterna entre la señal MediaMTX y un MP4 H.264/AAC en bucle para cada destino RTMP(S), sin registrar claves.

MediaMTX se ejecuta como servicio independiente. La publicacion preferida es WHIP y RTMP queda como fallback local; el navegador intenta WHEP/WebRTC y despues HLS. VDO.Ninja usa enlaces derivados que no se guardan en texto plano, QR en memoria e `iframe` con origen validado.

```powershell
docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml up -d --build
```

Consulta `docs/deployment.md` y `deployment/.env.example` antes de iniciar. HTTPS/WSS y secretos de entorno son obligatorios fuera de desarrollo local.

## Estructura del repositorio

```text
apps/api/           API FastAPI online
apps/frontend/      interfaz comercial React
apps/connector/     conector local OBS de telemetria y control autenticado
apps/media/         generador de respaldo y worker FFmpeg de retransmision
data/raw/           manifiesto, licencia y fuentes locales ignoradas por Git
data/interim/       transformaciones y metadatos regenerables
data/processed/     datasets finales de entrenamiento
models/registry/    modelos oficiales y artefactos verificables
notebooks/          preparacion, entrenamiento e inferencia documentados
reports/            fichas de los datasets
scripts/            preparacion, entrenamiento, evaluacion, demos y verificadores
src/streamml/       dominio, datos, entrenamiento, inferencia y servicios compartidos
infrastructure/      MediaMTX, nginx y Docker Compose
deployment/         configuracion de despliegue
docs/               documentacion operativa
tests/              pruebas unitarias, integracion, API, modelos y extremo a extremo
```

## Requisitos

- Git.
- Python 3.11 para datos, modelos, API y pruebas.
- Node.js 22 o posterior para el frontend.
- Docker Engine con Compose, FFmpeg y OBS Studio para el flujo completo de streaming.

## Instalacion

Se recomienda Python 3.11. En Windows:

```powershell
py -3.11 -m venv .venv311
.venv311\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Los entornos virtuales, secretos, caches, ZIP y CSV brutos grandes estan excluidos mediante `.gitignore`.

Para preparar y compilar el frontend con el lockfile versionado:

```powershell
Set-Location apps/frontend
npm ci
npm run build
Set-Location ../..
```

El conector de OBS tiene un paquete y dependencias independientes:

```powershell
python -m pip install -e apps/connector
streamml-connector --help
```

## Inicio local de desarrollo

1. Copia `.env.example` como `.env`, genera secretos aleatorios de al menos 32 caracteres y completa las variables requeridas. Para HTTP local, usa `STREAMML_COOKIE_SECURE=false` y `STREAMML_ENFORCE_HTTPS=false`; no desactives estas protecciones en un servidor.
2. Inicia la API desde la raiz:

   ```powershell
   python -m uvicorn apps.api.main:app --reload --env-file .env
   ```

3. En otra terminal, inicia el frontend:

   ```powershell
   Set-Location apps/frontend
   npm run dev
   ```

Para el despliegue integrado con nginx, MediaMTX y FFmpeg, utiliza `deployment/.env.example` y sigue `docs/deployment.md`. El conector local se vincula despues mediante un codigo temporal; su procedimiento completo tambien esta en esa guia.

## Flujo reproducible

```powershell
# Extrae del ZIP oficial solamente las sesiones predictivas requeridas.
python scripts\fetch_predictive_source.py

# Prepara los dos datasets versionados.
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
- Pruebas automatizadas: `53 passed`.
- Frontend React: compilacion de produccion correcta.
- Docker Compose: configuracion valida; las cuatro imagenes construidas y API/MediaMTX/worker iniciados correctamente.
- Verificador: `STREAMML RELEASE VERIFIED`.
- `git diff --check`: sin errores de whitespace.

## Limitaciones

- El predictivo usa capacidad de subida, perfil e historial; jitter y perdida se muestran y quedan disponibles para una futura version entrenada con esas variables.
- La sonda HTTP mide la ruta del computador con OBS al servidor, no sustituye las estadisticas WebRTC internas del tramo telefono–VDO.Ninja.
- Los cambios de parametros de perfil dependen de que la version y el modo de salida de OBS acepten `SetProfileParameter`; deben verificarse mientras el encoder esta activo.
- La fuente publica solo aporta 17 sesiones de al menos 20 minutos y un fuerte desbalance. La metrica predictiva perfecta no es evidencia suficiente para produccion.
- La ejecucion real de Docker, OBS, VDO.Ninja, WebRTC, RTMP(S) y las plataformas externas depende de servicios y credenciales que no forman parte de las pruebas aisladas.

## Seguridad

`.env` permanece excluido de Git. Los tres ejemplos versionados (`.env.example`, `deployment/.env.example` y `apps/frontend/.env.example`) contienen campos vacios, placeholders o valores publicos; nunca credenciales operativas. Las claves RTMP(S), contrasenas y tokens reales deben vivir unicamente en archivos ignorados, el keyring del sistema o el gestor de secretos del despliegue. Si una clave fue compartida, debe rotarse antes de publicar el repositorio.

El repositorio incluye `.github/workflows/ci.yml`, que repite las pruebas Python, la verificacion de modelos, el build del conector, el build del frontend y la validacion de Compose en cada `push` y `pull_request`.

Antes de publicar, el mismo flujo ejecuta `python scripts/check_no_secrets.py --history`. El control detecta archivos `.env` rastreados y firmas comunes de claves privadas y tokens sin imprimir sus valores.

La guia de [despliegue](docs/deployment.md) contiene el checklist de go-live, firewall, backup, actualizaciones y las pruebas fisicas obligatorias. La politica de reporte responsable se encuentra en [SECURITY.md](SECURITY.md).
