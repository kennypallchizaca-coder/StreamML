# StreamML

**Streaming Adaptativo y Predicción de Reducción de Calidad mediante Machine Learning**

**Integrantes:** Alexis Guaman y Cinthya Ramon.
**Inteligencia Artificial**

StreamML es un prototipo reproducible de streaming adaptativo. Mide la ruta de red, ejecuta modelos de Machine Learning supervisados y utiliza un agente determinista para mantener, aumentar o reducir el perfil de transmisión de video en OBS. Adicionalmente, cambia a una escena o archivo de respaldo cuando se pierde la señal y restaura el vivo tras un periodo estable.

La aplicación integra React, FastAPI, WebSocket, un conector local de OBS, MediaMTX, FFmpeg y Nginx. Este documento detalla la metodología científica detrás de los modelos, el proceso de entrenamiento documentado en cuadernos de experimentación (Notebooks), y las instrucciones operativas para desplegar el sistema en un entorno de producción.

> [!NOTE]
> Para una inmersión técnica profunda sobre cómo interactúan los microservicios y la explicación detallada de la estructura de cada carpeta del código, consulta el documento de [Arquitectura y Estructura del Proyecto](file:///c:/Users/kenny/OneDrive/Documents/STREAM-AI/Adaptive-Streaming-ai/docs/arquitectura-y-estructura.md) en el directorio `docs/`.

---

## 1. Identidad del Agente: Nexa

Nexa es la identidad visual y operativa del agente adaptativo de StreamML. No sustituye la lógica de control ni genera estados simulados, sino que traduce los estados operativos detallados a cinco posturas visuales: neutral, pensando, trabajando, éxito y error. En el monitor en vivo se expone por separado la decisión del modelo reactivo, la del modelo predictivo y la acción final ejecutada por el agente.

---

## 2. Objetivos de Machine Learning

### Modelo Reactivo
Clasifica una medición actual en uno de tres perfiles de transmisión: `low`, `medium`, `high`. Utiliza exactamente las siguientes variables instantáneas:
* `upload_mbps` (Velocidad actual de subida)
* `download_mbps` (Velocidad actual de descarga)
* `latency_ms` (Latencia actual)
El algoritmo seleccionado para este modelo es `DecisionTreeClassifier`, respondiendo en tiempo real (milisegundos) a fluctuaciones críticas de la red.

### Modelo Predictivo
Clasifica una ventana temporal en una de dos clases: `maintain` (mantener perfil) o `downgrade_needed` (reducción preventiva). 
Utiliza 19 estadísticas calculadas exclusivamente sobre **600 segundos históricos** (10 minutos) para predecir el comportamiento en los siguientes 600 segundos. El modelo utiliza regresión logística (`LogisticRegression`) y evalúa parámetros como pendiente, cambio de throughput, y percentiles de latencia, proveyendo un horizonte preventivo frente a la degradación de red.

---

## 3. Metodología y Cuadernos de Experimentación (Notebooks)

El desarrollo de los modelos se documentó secuencialmente en cuatro Notebooks de Jupyter. Aunque estos archivos fueron excluidos del entorno de producción para optimizar el despliegue, el proceso metodológico fue el siguiente:

* **01_data_preparation.ipynb**: Se extrajeron los datasets oficiales (26,686 filas para el modelo reactivo y 4,336 ventanas temporales para el predictivo), sin generar observaciones sintéticas. Los datos provienen de sesiones reales.
* **02_model_training.ipynb**: Ejecución del entrenamiento de los algoritmos. Se separaron estrictamente los conjuntos de entrenamiento, validación y prueba. La búsqueda de hiperparámetros se realizó con validación cruzada.
* **03_model_inference.ipynb**: Validación del comportamiento en frío y cálculo de las métricas finales (Macro F1, Balanced Accuracy).
* **04_entrenamiento_y_creacion_del_agente.ipynb**: Creación de las reglas operativas (cooldowns, márgenes de seguridad) para el agente determinista que interpreta las decisiones de los modelos.

**Resultados Oficiales:**
* **Modelo Reactivo**: 99.91% Macro F1 en el conjunto de pruebas.
* **Modelo Predictivo**: 100.00% Macro F1 en el conjunto de pruebas, utilizando un threshold validado de 0.50. (Nota metodológica: El resultado perfecto se atribuye a la limitada cantidad de sesiones públicas largas con clases desbalanceadas).

Los modelos serializados, métricas, contratos de variables y matrices de confusión se encuentran versionados en el directorio `models/registry/`.

---

## 4. Guía de Despliegue en Producción

El repositorio ha sido optimizado para servidores de producción, eliminando dependencias de experimentación.

### Requisitos Previos (Para el Servidor de Producción)
* Motor de contenedores Docker y Docker Compose.
* Dominio público y certificados SSL (requeridos para la correcta transmisión vía WebRTC sin retrasos).
* Intérprete de Bash (Linux/macOS) o PowerShell (Windows).

> [!IMPORTANT]
> **Separación de roles:** Toda la arquitectura anterior (Servidor Web, API, Modelos ML, Streaming) se ejecuta centralizada y aislada dentro de **Docker**. Sin embargo, el **Conector Local de OBS** (`apps/connector`) es el único componente que no va en el servidor: debe ser ejecutado en tu computadora local con Python para poder enviar comandos directamente al puerto local de tu OBS Studio.

### Proceso de Configuración e Instalación

El sistema provee un script de inicialización que abstrae la configuración del entorno.

1. **Ejecutar el Asistente de Configuración:**
   En Windows:
   ```powershell
   .\setup.ps1
   ```
   En Linux/macOS:
   ```bash
   bash setup.sh
   ```

2. **Ingresar Parámetros:**
   El asistente interactivo solicitará el dominio del servidor, las credenciales del administrador inicial y las rutas absolutas a los certificados SSL (`fullchain.pem` y `privkey.pem`). Las claves criptográficas internas se generarán automáticamente mediante entropía segura.

3. **Levantar los Servicios:**
   Una vez generado el archivo de entorno `.env`, se deben compilar e iniciar los contenedores:
   ```bash
   docker-compose -f infrastructure/docker/docker-compose.yml up -d
   ```

---

## 5. Operación y Mantenimiento

### Panel de Control
Acceda al dominio configurado a través del puerto 443 (HTTPS) mediante su navegador web. Inicie sesión con las credenciales establecidas durante la configuración. El panel proveerá las instrucciones y credenciales RTMP/WHEP necesarias para vincular el software de transmisión (OBS Studio) o cámaras móviles.

### Consideraciones sobre WebRTC y HLS
Si el servidor es desplegado en un entorno local (`localhost`) o se omite la configuración de los certificados SSL, el protocolo WebRTC será bloqueado por políticas de seguridad de los navegadores modernos. En este escenario, el reproductor de StreamML efectuará una transición automática al protocolo HLS. Este mecanismo garantiza la continuidad de la visualización, pero introducirá una latencia inherente de aproximadamente 10 segundos.

### Condiciones del Modelo Predictivo
El estado del modelo predictivo requiere exactamente 600 segundos (10 minutos) ininterrumpidos de telemetría de red. Durante el periodo de inicialización, el panel web no exhibirá datos predictivos; las decisiones operarán exclusivamente basadas en el modelo reactivo. 

### Respaldo y Restauración
La totalidad de la persistencia de datos (usuarios, telemetría y configuración) se almacena en el volumen mapeado al directorio local `deployment/` (archivo SQLite). Para efectuar un respaldo completo, copie este directorio tras haber detenido los servicios con `docker-compose down`.

### Recuperación de Credenciales
Todas las variables maestras de entorno residen en el archivo `.env` en la raíz del proyecto. Para restablecer el acceso administrativo, modifique la variable `STREAMML_BOOTSTRAP_PASSWORD`, guarde el archivo y reinicie los contenedores.
