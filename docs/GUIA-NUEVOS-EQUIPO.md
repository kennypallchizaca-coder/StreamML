# Guía Paso a Paso para Nuevos Miembros del Equipo (Onboarding Local)

¡Bienvenido al proyecto StreamML! Esta guía detallada te llevará paso a paso para configurar tu entorno de trabajo desde cero y ejecutar el proyecto en tu computadora. Está diseñada para que no te saltes ningún detalle importante.

---

## PASO 1: Instalación de Herramientas Base

Antes de descargar el código, asegúrate de tener instalados los siguientes programas en tu máquina. Si te falta alguno, descárgalo e instálalo:

1. **Git**: Para el control de versiones. [Descargar Git](https://git-scm.com/downloads)
2. **Docker Desktop**: Esencial para correr servicios como nuestra base de datos, caché o MediaMTX. 
   - [Descargar Docker Desktop](https://www.docker.com/products/docker-desktop)
   - *Nota para Windows:* Asegúrate de tener instalado y habilitado WSL2.
3. **Python 3.11 o superior**: Para ejecutar nuestro Backend (API).
   - [Descargar Python](https://www.python.org/downloads/)
   - *Importante (Windows):* Durante la instalación, marca la casilla **"Add Python to PATH"**.
4. **Node.js (versión 22 o superior)**: Para ejecutar nuestro Frontend web (React/Vite).
   - [Descargar Node.js](https://nodejs.org/)
5. **Editor de Código**: Te recomendamos [Visual Studio Code (VSCode)](https://code.visualstudio.com/).
   - *Extensiones recomendadas:* Python, Pylance, Ruff, ESLint, Prettier, Docker.

---

## PASO 2: Clonar el Repositorio

Abre tu terminal (Símbolo del sistema, PowerShell o Terminal de Mac/Linux) y ejecuta:

```bash
# 1. Clonar el repositorio principal
git clone https://github.com/kennypallchizaca-coder/STREAM-MACHINELEARNING.git

# 2. Entrar a la carpeta principal
cd STREAM-MACHINELEARNING

# 3. Entrar a la carpeta del proyecto específico
cd Adaptive-Streaming-ai
```

> **Aviso:** Todo el trabajo y comandos posteriores deben ejecutarse dentro de la carpeta `Adaptive-Streaming-ai`.

---

## PASO 3: Elegir el Modo de Ejecución

Existen dos formas principales de correr el proyecto. Elige la que mejor se adapte a tu rol:

- **Opción A (Vía Rápida):** Levanta todo en Docker. Ideal si eres QA, Analista de Datos, o solo quieres ver la aplicación funcionando sin programar.
- **Opción B (Desarrollo Nativo):** Levanta el Backend y Frontend nativamente. Ideal si eres Programador y necesitas *Hot-Reload* (que los cambios de código se reflejen inmediatamente).

---

### Opción A: Vía Rápida (Recomendado para Pruebas o Demos)

Esta opción levanta absolutamente todo (API, Frontend, MediaMTX) usando contenedores. 

**Pasos:**
1. Abre tu aplicación de **Docker Desktop** y asegúrate de que el motor de Docker esté encendido (el icono en la barra de tareas debe estar verde).
2. En tu terminal (dentro de `Adaptive-Streaming-ai`), ejecuta:
   ```bash
   docker compose -f infrastructure/docker/docker-compose.local.yml up --build
   ```
3. Espera un par de minutos a que se descarguen las imágenes y se compilen los servicios.
4. Cuando veas que los logs se estabilizan, abre tu navegador y visita: **[http://localhost](http://localhost)**
5. Inicia sesión con las credenciales por defecto configuradas para pruebas locales:
   - **Correo:** `admin@localhost`
   - **Contraseña:** `password123456`

Para **detener** el sistema, presiona `Ctrl + C` en tu terminal, o ejecuta:
```bash
docker compose -f infrastructure/docker/docker-compose.local.yml down
```

---

### Opción B: Flujo de Desarrollo Nativo (Recomendado para Programadores)

Esta es la forma estándar de desarrollar en StreamML. Aprovecharás tus herramientas locales para compilar más rápido.

#### 1. Correr la Infraestructura Base
Primero, necesitamos correr MediaMTX (nuestro servidor de streaming) usando Docker.
```bash
docker compose -f infrastructure/docker/docker-compose.local.yml up mediamtx media-init -d
```
> Esto levantará silenciosamente MediaMTX en el puerto `1935` (RTMP) y `8889` (WebRTC).

#### 2. Configurar y Levantar la API (Backend)
Abre una terminal nueva en `Adaptive-Streaming-ai`.

```bash
# a. Crear el entorno virtual de Python
python -m venv .venv

# b. Activar el entorno virtual
# En Windows (PowerShell):
.venv\Scripts\Activate.ps1
# En Linux/Mac:
source .venv/bin/activate

# c. Instalar los paquetes del proyecto
pip install -r requirements.txt

# d. Configurar el archivo .env
# Copiamos el archivo de ejemplo a uno real local
cp .env.example .env
```

Abre el archivo `.env` recién creado en tu editor y asegúrate de que contenga valores para desarrollo. Para correr localmente, deberías reemplazar el valor de entorno por development y asegurarte de tener un origen local.
*(Nota: El archivo `docker-compose.local.yml` ya inyectaba esto, pero al correr nativo dependes de este archivo `.env`)*

```bash
# e. Ejecutar servidor de desarrollo con Hot-Reload
python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```
> La API estará escuchando en `http://localhost:8000`. Si editas algún archivo `.py`, el servidor se reiniciará automáticamente.

#### 3. Configurar y Levantar el Frontend (Web)
Abre otra terminal nueva (la tercera).

```bash
# a. Navegar al directorio del frontend
cd apps/frontend

# b. Instalar dependencias de Node.js
npm install

# c. Configurar las rutas de la API para Vite
# En Windows (PowerShell):
$env:VITE_API_BASE_URL="http://localhost:8000/api/v1"
$env:VITE_WS_BASE_URL="ws://localhost:8000/ws"

# En Linux/Mac (Bash):
export VITE_API_BASE_URL="http://localhost:8000/api/v1"
export VITE_WS_BASE_URL="ws://localhost:8000/ws"

# d. Iniciar el servidor de desarrollo del Frontend
npm run dev
```
> El frontend estará disponible usualmente en `http://localhost:5173`. Abre ese enlace en tu navegador.
> 
> *Nota: Ya que estás corriendo los servicios de manera nativa sin el proxy de Nginx, accederás a la web mediante el puerto 5173 y las peticiones viajarán directo al puerto 8000 de tu API.*

---

## PASO 4: Mejores Prácticas y Contribución

### 1. Formateo de Código (Python)
Utilizamos **Ruff** para asegurar que todo nuestro código Python siga las mismas reglas de estilo. Antes de enviar tu código a revisión (commit), siempre ejecuta:
```bash
ruff check . --fix
```
Esto corregirá automáticamente importaciones, comillas y errores comunes de formato.

### 2. Pruebas Unitarias (Tests)
Es vital asegurar que no hemos roto funcionalidades existentes. Ejecuta todas las pruebas usando:
```bash
python -m pytest
```
Si todas las pruebas pasan de color verde, tu código está listo.

### 3. Archivo `.gitignore`
Nunca hagas commit de archivos con secretos (`.env`), carpetas temporales (`__pycache__`, `.venv`, `node_modules`) ni bases de datos locales (`streamml.sqlite3`). El proyecto ya cuenta con un `.gitignore` configurado; asegúrate de respetarlo.

¡Felicidades! Tu entorno ya está listo. Si tienes dudas, abre un Issue en el repositorio o habla con tu Tech Lead.
