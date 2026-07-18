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
.\.venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Los entornos virtuales, secretos, caches, ZIP y CSV brutos grandes estan excluidos mediante `.gitignore`.

Para preparar y compilar el frontend con el lockfile versionado:

```powershell
Set-Location apps/frontend
npm ci
npm test
npm run build
Set-Location ../..
```

El conector de OBS tiene un paquete y dependencias independientes:

```powershell
python -m pip install -e apps/connector
streamml-connector --help
```

En Windows, el asistente gráfico evita estos comandos para la configuración diaria: abre con doble clic `scripts\Abrir-Configuracion-StreamML.cmd`. Consulta [la guía de configuración gráfica](docs/configuracion-gui.md) para vincular OBS, iniciar Docker, renovar credenciales y crear copias de seguridad sin exponer secretos.

## Inicio local de desarrollo

1. Copia `.env.example` como `.env`, usa `STREAMML_ENVIRONMENT=development`, genera secretos aleatorios de al menos 32 caracteres y completa las variables requeridas. Para HTTP local, usa `STREAMML_COOKIE_SECURE=false` y `STREAMML_ENFORCE_HTTPS=false`; no desactives estas protecciones en un servidor. El `.env` está ignorado por Git. Para operación normal y producción, introduce secretos desde el asistente gráfico para guardarlos cifrados en el almacén del sistema.
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

## Prueba del sistema paso a paso

La prueba se divide en tres niveles. Completa primero la prueba local, después la integración con OBS/VDO.Ninja y finalmente, si tienes dominio y certificado, el flujo Docker equivalente a producción.

### 1. Preparar el entorno local

Desde la raíz del repositorio:

```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install --upgrade pip
.\.venv311\Scripts\python.exe -m pip install -r requirements.txt -e apps/connector
Set-Location apps/frontend
npm ci
Set-Location ../..
```

Copia `.env.example` como `.env` y completa los valores locales. Los dos secretos deben ser diferentes y tener más de 32 caracteres. La configuración mínima de desarrollo es:

```dotenv
STREAMML_ENVIRONMENT=development
STREAMML_TOKEN_SECRET=PEGA_AQUI_EL_PRIMER_VALOR_ALEATORIO_DE_MAS_DE_32_CARACTERES
STREAMML_MEDIA_AUTH_SECRET=PEGA_AQUI_OTRO_VALOR_ALEATORIO_DIFERENTE
STREAMML_ALLOWED_ORIGINS=http://127.0.0.1:5173
STREAMML_DATABASE_PATH=deployment/streamml.local.sqlite3
STREAMML_MEDIAMTX_PUBLIC_BASE=http://127.0.0.1:8888
STREAMML_MEDIAMTX_RTMP_PUBLISH_BASE=rtmp://127.0.0.1:1935
STREAMML_BOOTSTRAP_EMAIL=admin@local.test
STREAMML_BOOTSTRAP_PASSWORD=DEFINE_UNA_CLAVE_LOCAL_DE_AL_MENOS_12_CARACTERES
STREAMML_COOKIE_SECURE=false
STREAMML_ENFORCE_HTTPS=false
```

No confirmes `.env`: está ignorado por Git. Para generar valores aleatorios localmente puedes ejecutar dos veces este comando y utilizar un resultado distinto en cada secreto:

```powershell
[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
```

### 2. Iniciar API, dashboard y asistente

Abre tres terminales.

Terminal 1, desde la raíz:

```powershell
.\.venv311\Scripts\python.exe -m uvicorn apps.api.main:app --reload --env-file .env
```

Terminal 2:

```powershell
Set-Location apps/frontend
npm run dev
```

Terminal 3, o mediante doble clic:

```powershell
scripts\Abrir-Configuracion-StreamML.cmd
```

Comprueba estos enlaces:

| Componente | URL | Resultado esperado |
|---|---|---|
| API | `http://127.0.0.1:8000/health` | `status: ok`, `ready: true`, base y modelos disponibles |
| Dashboard | `http://127.0.0.1:5173` | Formulario de inicio de sesión |
| Asistente local | `http://127.0.0.1:8765` | Pestañas de OBS, servidor Docker y ayuda |

En desarrollo es correcto que `/health` muestre `production_ready: false`: HTTP y las cookies locales no son controles de producción.

#### Navegación de la GUI

Después de iniciar sesión, el **Centro de control** muestra únicamente datos reales: transmisiones registradas, sesiones activas, predicciones disponibles y última actividad. La navegación lateral se divide en **Operación**, **Inteligencia** y **Sistema**. Usa `Ctrl+K` (o `Cmd+K` en macOS) para buscar y abrir cualquier sección, y el botón de tema de la barra superior para alternar entre modo oscuro y claro; la preferencia se guarda en la cuenta. En pantallas pequeñas, abre el menú con el botón situado en la esquina superior izquierda.

El panel web y el asistente local comparten el tema global de `apps/frontend/src/theme.css`, incluidos los colores semánticos de éxito, advertencia, error e información. El enlace **Abrir conector** transmite el tema activo al asistente, que también permite alternarlo desde su propia barra superior.

### 3. Preparar OBS Studio

1. Abre OBS y entra en **Herramientas → Configuración del servidor WebSocket**.
2. Activa el servidor WebSocket, conserva `4455` si está disponible o elige otro puerto libre y define una contraseña. El asistente debe usar exactamente el mismo puerto que muestra OBS.
3. No publiques el puerto WebSocket en el router. El host utilizado por el conector debe ser `127.0.0.1` o `localhost`.
4. Crea una escena llamada `StreamML Live`.
5. Crea otra escena llamada `StreamML Backup`.
6. En `StreamML Backup`, agrega una **Fuente multimedia** con un MP4 en bucle, o una imagen mediante **Fuente de imagen**.
7. En `StreamML Live`, agrega una **Fuente de navegador** para el enlace de visualización de VDO.Ninja.

### 4. Conectar el teléfono con VDO.Ninja

Puedes utilizar el enlace generado por StreamML o el que entrega la aplicación VDO.Ninja del teléfono:

1. Abre VDO.Ninja en el teléfono y comienza a compartir la cámara.
2. Copia el enlace de visualización o sala. Un enlace de visualización normalmente contiene `view=`; no pegues en StreamML un enlace `push=`, porque ese es el enlace emisor del teléfono.
3. En StreamML crea una transmisión y selecciona la opción para usar un enlace existente si el enlace proviene de la aplicación móvil.
4. Pega el enlace `view` o `room` en StreamML y valida la vista previa.
5. Usa ese mismo enlace como URL de la Fuente de navegador dentro de `StreamML Live`.

El enlace aparece en StreamML y en OBS porque son dos consumidores distintos: StreamML lo valida y muestra la vista previa, mientras OBS captura realmente el video que será codificado y transmitido.

### 5. Crear y vincular una transmisión

1. Abre `http://127.0.0.1:5173` e inicia sesión con `STREAMML_BOOTSTRAP_EMAIL` y `STREAMML_BOOTSTRAP_PASSWORD`.
2. Pulsa **Nueva transmisión**, define un nombre y completa el método VDO.Ninja.
3. En el paso **Comprobación**, genera el código temporal sin abandonar el asistente de nueva transmisión. También puedes generarlo después en **Configuración → Conexiones**.
4. Abre el asistente local desde ese mismo paso o en `http://127.0.0.1:8765`.
5. Completa los campos de OBS:

   | Campo | Valor local recomendado |
   |---|---|
   | URL de la API | `http://127.0.0.1:8000` |
   | Nombre del conector | Un nombre reconocible, por ejemplo `OBS Alexis` |
   | Host de OBS | `127.0.0.1` |
   | Puerto | El mismo que muestra OBS (`4455` normalmente) |
   | Escena en vivo | `StreamML Live` |
   | Escena de respaldo | `StreamML Backup` |
   | Telemetría | `1` segundo |
   | Prueba de red | `5` segundos y `262144` bytes |

6. Escribe la contraseña de OBS y el código temporal.
7. Antes de guardar, pulsa **Comprobar conexión**. La GUI comprueba los valores visibles aunque todavía no estén guardados.
8. Debes obtener API disponible, código listo/vinculación correcta y OBS conectado con las dos escenas encontradas.
9. Pulsa **Guardar y vincular** y después **Iniciar monitorización**. La aplicación detecta el vínculo y habilita **Abrir monitoreo**.

Los códigos temporales son de un solo uso y cada vinculación pertenece a una transmisión concreta. Si se vincula un código nuevo mientras el monitor está activo, el asistente reinicia el conector automáticamente para cargar el token nuevo; ya no es necesario detenerlo manualmente. Si el código caduca o se consume, genera otro desde el flujo de transmisión o desde Configuración.

### 6. Comprobar telemetría y modelos

1. Abre la transmisión y entra en **Monitor en vivo**. El distintivo solo dice **EN VIVO** si OBS informa que su salida está activa; antes muestra **OBS LISTO** o **ESPERANDO SEÑAL**.
2. Inicia la salida de OBS o una grabación/prueba que produzca estadísticas del codificador.
3. Espera entre 5 y 15 segundos.
4. Confirma que cambien FPS, bitrate de salida, frames omitidos y congestión.
5. Confirma que aparezcan subida, descarga, latencia y jitter después de la primera prueba HTTP.
6. El modelo reactivo debe recomendar `low`, `medium` o `high` con las condiciones actuales.
7. El predictivo necesita aproximadamente 600 muestras históricas: espera al menos 10 minutos de telemetría continua para obtener `maintain` o `downgrade_needed`.
8. Revisa en **Historial** que la sesión, telemetría, predicciones y decisiones se mantengan después de reiniciar la API.

Para una prueba física de adaptación, utiliza un hotspot móvil y reduce gradualmente la cobertura o limita la subida. Verifica que el agente reduzca un nivel antes de una interrupción, respete el cooldown y no oscile rápidamente entre perfiles. No uses una transmisión pública importante durante esta prueba.

### 7. Probar respaldo y recuperación

1. Mantén OBS abierto y WebSocket conectado.
2. Inicia la transmisión desde OBS y confirma la escena `StreamML Live`.
3. Detén la salida de streaming de OBS, pero no cierres OBS.
4. Comprueba que el sistema marque pérdida de señal y active `StreamML Backup` después del tiempo configurado.
5. Inicia nuevamente la salida de OBS.
6. Mantén la señal estable durante el periodo de recuperación.
7. Comprueba que el sistema restaure `StreamML Live` y registre ambas decisiones.

Cuando se usa el worker FFmpeg de producción, también debes confirmar que el destino RTMP(S) continúa recibiendo `/fallback/fallback.mp4` durante la pérdida y vuelve al vivo después de tres comprobaciones correctas.

### 8. Probar el despliegue Docker

La forma recomendada es **Asistente local → Servidor Docker**. Completa dominio HTTPS, certificado, correo administrador, contraseña y destinos; pulsa **Guardar servidor**, **Validar Docker Compose** e **Iniciar o actualizar servicios**.

La alternativa por terminal es:

```powershell
Copy-Item deployment/.env.example deployment/.env
# Edita deployment/.env con valores reales y rutas TLS válidas.
docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml config --quiet
docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml up -d --build --wait
docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml ps
```

API, frontend, MediaMTX, media-worker y nginx deben aparecer `healthy`; `media-init` debe finalizar con código `0`. En `https://TU_DOMINIO/health`, `production_ready` debe ser `true`.

Usa la URL RTMP o WHIP devuelta por la transmisión para configurar OBS. Después valida en orden: publicación OBS → MediaMTX, reproducción WHEP/WebRTC, HLS de respaldo y retransmisión hacia YouTube/Twitch/Facebook/Kick.

### 9. Ejecutar las pruebas automatizadas

Desde la raíz:

```powershell
.\.venv311\Scripts\python.exe -m pytest -q
.\.venv311\Scripts\python.exe -m ruff check apps src scripts tests
.\.venv311\Scripts\python.exe scripts/verify_release.py
.\.venv311\Scripts\python.exe scripts/demo_models.py
.\.venv311\Scripts\python.exe scripts/check_no_secrets.py --history
Set-Location apps/frontend
npm test
npm run lint
npm run build
npm audit --omit=dev --audit-level=high
Set-Location ../..
docker compose --env-file deployment/.env.example -f infrastructure/docker/docker-compose.yml config --quiet
```

Resultado de referencia: `71 passed` en Python, 12 pruebas frontend aprobadas, lint Python/TypeScript limpio, `STREAMML RELEASE VERIFIED`, cero vulnerabilidades npm de producción y Compose válido.

### 10. Detener la prueba

En el asistente pulsa **Detener monitorización**. Detén API y frontend con `Ctrl+C`. Para Docker:

```powershell
docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml down
```

No agregues `--volumes`: eliminaría la base persistente. Para crear una copia consistente antes de actualizar utiliza:

```powershell
.\scripts\Backup-StreamML.ps1
```

Si algo falla, consulta [configuración gráfica](docs/configuracion-gui.md) y [despliegue y recuperación](docs/deployment.md).

## Verificación completa

Desde la raíz del repositorio:

```powershell
.\.venv311\Scripts\python.exe -m pytest -q
.\.venv311\Scripts\python.exe -m ruff check apps src scripts tests
.\.venv311\Scripts\python.exe -m compileall -q apps src scripts
.\.venv311\Scripts\python.exe scripts/verify_release.py
.\.venv311\Scripts\python.exe scripts/demo_models.py
.\.venv311\Scripts\python.exe scripts/check_no_secrets.py --history
Set-Location apps/frontend
npm ci
npm test
npm run lint
npm run build
Set-Location ../..
docker compose --env-file deployment/.env.example -f infrastructure/docker/docker-compose.yml config --quiet
docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml build
```

Las migraciones y la inicialización de la base se ejecutan automáticamente al arrancar la API. Los endpoints `/health/live`, `/health/ready` y `/health` separan vida, preparación y diagnóstico. En producción, `production_ready` solo es verdadero si la base, el esquema, los modelos verificados y los controles HTTPS están listos.

Consulta [configuración gráfica](docs/configuracion-gui.md), [despliegue y recuperación](docs/deployment.md), [decisiones técnicas](docs/decisiones-tecnicas.md) y el [informe de revisión final](reports/final_review.md).

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
- Pruebas automatizadas: `71 passed` y lint Python limpio.
- Frontend React: 12 pruebas unitarias, lint TypeScript/React limpio, auditoria sin vulnerabilidades de produccion y compilacion correcta.
- Docker Compose: configuracion valida; imagenes construidas y API, frontend, MediaMTX, worker y nginx saludables en la prueba equivalente a produccion.
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
