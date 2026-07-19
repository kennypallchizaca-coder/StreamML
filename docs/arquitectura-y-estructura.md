# Arquitectura y Estructura del Proyecto StreamML

Este documento detalla la arquitectura técnica de alto nivel de StreamML, cómo interactúan sus diferentes microservicios y la organización de carpetas del código fuente.

---

## 1. Arquitectura del Sistema

StreamML no es un solo programa monolítico, sino una arquitectura distribuida orientada a eventos, diseñada para manejar transmisiones de video en vivo (baja latencia) y predicciones de Inteligencia Artificial simultáneamente.

El sistema se compone de los siguientes módulos principales:

### A. Backend y Orquestador (FastAPI)
El núcleo inteligente del proyecto. Expone una API REST para la gestión de usuarios, sesiones y configuraciones, y un servidor de WebSockets de alto rendimiento que recibe datos de telemetría de red varias veces por segundo. Aquí reside el motor de inferencia de Machine Learning, el cual evalúa los datos de red usando los modelos pre-entrenados y delega las decisiones al **Agente Nexa**.

### B. Interfaz Gráfica (React + TypeScript)
Una aplicación de una sola página (SPA) responsiva que provee el Panel de Control. Se comunica con el backend vía HTTP (para configuraciones) y WebSockets (para recibir el estado en tiempo real de Nexa y la telemetría).

### C. Servidor de Medios (MediaMTX + FFmpeg)
MediaMTX se encarga de recibir el flujo de video (vía RTMP/WHIP) proveniente de OBS. FFmpeg actúa como un "trabajador de medios" en segundo plano; si el sistema detecta que el internet del streamer se cortó, FFmpeg interviene e inyecta un video de "Respaldo / Problemas Técnicos" hacia los espectadores.

### D. Conector Local de OBS (Python)
Es un script ligero que el usuario ejecuta en su computadora (donde tiene instalado OBS Studio). Su única misión es conectarse al OBS de forma local, recibir instrucciones del Backend a través de la nube, y ejecutar cambios en OBS (cambiar la calidad del video o cambiar de escena) de forma instantánea.

### E. Proxy Inverso (Nginx)
Punto de entrada único. Gestiona la seguridad, los certificados SSL (HTTPS), expone el frontend y enruta las solicitudes hacia el Backend API o el Servidor de Medios (WebRTC) según corresponda.

---

## 2. Estructura de Directorios

El código fuente está modularizado cuidadosamente siguiendo principios de diseño impulsado por el dominio (Domain-Driven Design). A continuación se explica cada carpeta principal del repositorio:

```text
StreamML/
├── apps/                        # Puntos de entrada ejecutables (Microservicios)
│   ├── api/                     # Aplicación FastAPI (Rutas, esquemas, dependencias).
│   ├── connector/               # Conector local para OBS WebSocket y GUI de setup.
│   ├── frontend/                # Código fuente de la interfaz gráfica web en React.
│   └── media/                   # Scripts de manejo de FFmpeg (restream_worker.py).
│
├── docs/                        # Documentación Técnica Extendida
│   ├── arquitectura-y-estructura.md (Este archivo).
│   ├── decisiones-tecnicas.md   # Justificación del diseño de seguridad y ML.
│   ├── configuracion-gui.md     # Guía sobre la UI del conector local.
│   └── deployment.md            # Guía antigua/extendida de despliegue.
│
├── infrastructure/              # Archivos de Despliegue y Sistemas
│   ├── docker/                  # Dockerfiles por cada app y el docker-compose.yml.
│   ├── mediamtx/                # Archivo de configuración de rutas de MediaMTX.
│   └── nginx/                   # Configuración del proxy inverso y plantillas.
│
├── models/registry/             # Modelos de Machine Learning Serializados
│   ├── predictive/              # Modelo de regresión logística (10 mins).
│   └── reactive/                # Modelo de árbol de decisiones (milisegundos).
│
├── src/streamml/                # Lógica de Negocio Central (Core) compartida
│   ├── agent/                   # Lógica determinista (cooldowns, policy) de Nexa.
│   ├── data/                    # Contratos y adaptadores de datos limpios.
│   ├── domain/                  # Entidades de dominio.
│   ├── evaluation/              # Scripts de evaluación y auditoría métrica.
│   ├── features/                # Construcción matemática de la ventana predictiva.
│   ├── inference/               # Motor de inferencia para ejecutar los modelos `.joblib`.
│   ├── security/                # Criptografía, validación de tokens y firmas.
│   └── services/                # Servicios orquestadores (Database, SessionStore).
│
├── deployment/                  # (Generado dinámicamente) Volumen de persistencia.
│   └── streamml.sqlite3         # Base de datos principal de producción.
│
├── tests/                       # Suite de Pruebas Automatizadas (Pytest)
│   ├── api/                     # Pruebas a las rutas REST de FastAPI.
│   ├── integration/             # Pruebas combinadas (API + Conector).
│   └── unit/                    # Pruebas aisladas para lógica central (src/streamml).
│
├── setup.ps1 / setup.sh         # Asistentes interactivos de configuración para producción.
├── .env.example                 # Plantilla de variables de entorno seguras.
├── README.md                    # Documentación principal de usuario.
└── requirements.txt             # Dependencias ligeras exclusivas de producción.
```

---

## 3. Flujo de Toma de Decisiones (Ciclo de Vida)

1. El teléfono del usuario envía su telemetría local (VDO.Ninja) al **Frontend**, quien lo transmite al **Backend** por WebSocket.
2. El servicio `telemetry.py` consolida los datos y alimenta el motor de inferencia en `src/streamml/inference/`.
3. El **Modelo Reactivo** emite su evaluación en milisegundos basándose en la muestra actual. Simultáneamente, si existen 10 minutos de datos en memoria, el **Modelo Predictivo** evalúa la tendencia futura.
4. Las predicciones de ambos modelos llegan al **Agente Determinista** (`src/streamml/agent/policy.py`). El agente aplica filtros de seguridad (ej: no bajar la calidad si ya la bajamos hace menos de 10 segundos).
5. Si el Agente decide ejecutar una acción, envía la instrucción firmada a la cola.
6. El **Conector Local de OBS**, que siempre está escuchando, recibe la instrucción y cambia instantáneamente el perfil de transmisión o la escena de respaldo a través de OBS WebSocket.
