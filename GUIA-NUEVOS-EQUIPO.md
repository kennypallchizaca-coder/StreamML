# Guía para Nuevos Miembros del Equipo (Onboarding Local)

¡Bienvenido al proyecto StreamML! Esta guía te ayudará a configurar y ejecutar el entorno de desarrollo localmente en tu computadora.

Existen dos formas principales de correr el proyecto, dependiendo de tus necesidades:

---

## Opción 1: Vía Rápida (Recomendado para Pruebas, QA o Demos)

Esta opción levanta todo el ecosistema (API, Frontend, MediaMTX) usando Docker. Es la forma más rápida de tener la aplicación corriendo sin instalar dependencias locales, pero **no** cuenta con recarga en caliente (hot-reload) para desarrollo.

### Prerrequisitos
- Tener **Docker** y **Docker Compose** instalados y funcionando.

### Pasos
1. Abre tu terminal en el directorio raíz del proyecto (`Adaptive-Streaming-ai`).
2. Ejecuta el archivo de Docker Compose orientado a desarrollo local:
   ```bash
   docker compose -f infrastructure/docker/docker-compose.local.yml up --build
   ```
3. Una vez que todos los contenedores reporten estar "Healthy", la aplicación estará disponible en:
   - **Frontend web:** `http://localhost`
   - **Credenciales por defecto:**
     - Correo: `admin@localhost`
     - Contraseña: `password123456`

Para detener el ecosistema, simplemente presiona `Ctrl+C` en la terminal o ejecuta:
```bash
docker compose -f infrastructure/docker/docker-compose.local.yml down
```

---

## Opción 2: Flujo de Desarrollo Nativo (Recomendado para Programadores)

Esta es la forma estándar de desarrollar en StreamML. Ejecutaremos el motor de medios (`MediaMTX`) en Docker, pero la API (Python) y el Frontend (Node.js) se correrán nativamente en tu máquina. Esto te permite disfrutar del *Hot-Reload* y usar el depurador de tu IDE sin penalizaciones de rendimiento.

### Prerrequisitos
- **Python 3.11+**
- **Node.js 22+** y `npm`
- **Docker** (solo para servicios de infraestructura)

### 1. Configurar y levantar la Infraestructura
Primero, necesitamos correr MediaMTX (nuestro servidor de streaming):
```bash
docker compose -f infrastructure/docker/docker-compose.local.yml up mediamtx media-init -d
```
> Esto levantará MediaMTX en el puerto `1935` (RTMP) y `8889` (WebRTC) en tu máquina local.

### 2. Levantar la API (Backend)
En una nueva terminal, configura el entorno de Python:
```bash
# 1. Crear entorno virtual
python -m venv .venv

# 2. Activar entorno virtual
# En Windows (PowerShell):
.venv\Scripts\Activate.ps1
# En Linux/Mac:
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno locales
# Copia el ejemplo y renómbralo a .env (para que uvicorn lo cargue)
cp .env.example .env

# 5. Ejecutar servidor de desarrollo con Hot-Reload
python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```
> La API estará escuchando en `http://localhost:8000`.

### 3. Levantar el Frontend
En otra terminal, configura y ejecuta la aplicación web de React/Vite:
```bash
# 1. Navegar al directorio del frontend
cd apps/frontend

# 2. Instalar paquetes NPM
npm install

# 3. Configurar variables de Vite (apuntando a la API local)
export VITE_API_BASE_URL="http://localhost:8000/api/v1"
export VITE_WS_BASE_URL="ws://localhost:8000/ws"
# (En Windows PowerShell usa: $env:VITE_API_BASE_URL="...")

# 4. Ejecutar servidor de desarrollo
npm run dev
```
> El frontend estará disponible usualmente en `http://localhost:5173`. 
> 
> *Nota: Como estás corriendo sin el Nginx inverso en este modo, debes acceder directamente a los puertos del frontend y la API.*

---

## Preguntas Frecuentes (FAQ)

### ¿Por qué no usar el `docker-compose.yml` estándar?
El archivo `docker-compose.yml` base está diseñado estrictamente para **Producción**. Exige certificados SSL reales, fuerza HTTPS y usa cookies seguras (`Secure=True`), lo que hará que el login falle si lo intentas usar en `localhost` a través de HTTP. Siempre usa `docker-compose.local.yml` para el desarrollo.

### ¿Cómo formateo mi código antes de hacer un commit?
El proyecto utiliza `ruff` para estandarizar el código Python. Ejecuta:
```bash
ruff check . --fix
```
Para Node.js, asegúrate de correr el linter configurado en el `package.json` de la carpeta frontend.

¡Feliz codificación! Si encuentras algún problema, consulta a los líderes del proyecto o abre un Issue en el repositorio.
