# Guía de Demostración — StreamML

**Duración estimada:** 5 minutos  
**Requisitos:** OBS Studio abierto, VDO.Ninja transmitiendo, MediaMTX ejecutándose

---

## Paso 1: Mostrar el README (30 segundos)

Abrir el archivo `README.md` y señalar:
- Nombre del proyecto y autores.
- La tabla de estado actual (componentes activos vs pendientes).
- La advertencia de que no es un sistema de producción.

**Frase sugerida:**
> "Nuestro proyecto utiliza Machine Learning para analizar condiciones de red y recomendar el perfil de calidad óptimo durante una transmisión en vivo."

## Paso 2: Explicar los dos modelos (45 segundos)

Señalar la sección de Arquitectura:
- **Modelo reactivo (DecisionTree):** Analiza el estado actual (upload, download, latencia) y clasifica en low/medium/high. Macro F1 de 0.9977.
- **Modelo predictivo (RandomForest):** Analiza una ventana de 120 segundos (19 features estadísticos) y predice si habrá degradación. Macro F1 de 0.4950 con generalization gap de 0.1002.

**Frase sugerida:**
> "El modelo reactivo aprendió nuestra heurística de reglas con alta precisión. El modelo predictivo supera al baseline pero tiene un recall limitado, por eso aún no controla la transmisión."

## Paso 3: Mostrar artefactos congelados (30 segundos)

Abrir el directorio `models/phase1_final_release/` y mostrar:
- Los 7 archivos (modelos, preprocesadores, metadatos, contrato, manifiesto).
- Explicar que están verificados con hashes SHA-256.

Ejecutar:
```bash
python scripts/verify_phase1_release.py
```

Esperar el mensaje: `PHASE 1 RELEASE VERIFIED`

## Paso 4: Mostrar OBS recibiendo video (30 segundos)

Mostrar la ventana de OBS Studio con:
- La fuente de VDO.Ninja activa (video en vivo desde el teléfono).
- La configuración de salida RTMP apuntando a MediaMTX.

## Paso 5: Mostrar OBS transmitiendo hacia MediaMTX (15 segundos)

Verificar que OBS está transmitiendo activamente:
- El indicador de streaming activo en la barra inferior de OBS.
- Opcionalmente, abrir `http://localhost:9997/` para ver el panel de MediaMTX.

## Paso 6: Ejecutar sesión de recolección (60 segundos)

Ejecutar en la terminal:
```bash
python scripts/run_data_collection_session.py --duration 30 --profile high --condition stable
```

Observar la salida en tiempo real mostrando:
- El número de muestra
- El perfil actual
- El bitrate
- Los FPS
- Los frames totales

Esperar 30 segundos hasta que termine.

## Paso 7: Mostrar el CSV generado (30 segundos)

Abrir el archivo CSV generado en `data/telemetry/raw/` (el más reciente).
Señalar las columnas clave:
- `timestamp_utc`: marca temporal de cada observación.
- `upload_mbps`, `download_mbps`: métricas de red.
- `latency_ms`: latencia medida.
- `fps`, `dropped_frames`: métricas de video.
- `action_applied`: siempre `none` (sin intervención automática).

## Paso 8: Mostrar metadatos (30 segundos)

Abrir el archivo JSON de metadatos en `data/telemetry/metadata/`.
Señalar:
- `validation_status: "valid"` — la sesión pasó todas las comprobaciones.
- `samples_recorded: 30` — se registraron 30 muestras.
- `invalid_rows: 0` — ninguna fila con errores.
- `timestamp_errors: 0` — todos los timestamps son válidos.
- `models_executed: false` — los modelos NO se ejecutaron.

## Paso 9: Explicar por qué los modelos están desactivados (30 segundos)

**Frase sugerida:**
> "En esta fase los modelos están desactivados intencionalmente. La telemetría que recolectamos utiliza features distintos a los del entrenamiento original. Necesitamos acumular suficientes datos reales para validar si los modelos son transferibles o si requieren reentrenamiento. El bitrate de OBS no es un indicador de capacidad de red; es la tasa de codificación configurada."

## Paso 10: Mostrar resultados de pruebas (30 segundos)

Ejecutar:
```bash
pytest -v
```

Mostrar que las 38 pruebas pasan correctamente.

Opcionalmente ejecutar:
```bash
python scripts/check_presentation_ready.py
```

Esperar el mensaje: `PRESENTATION READY`

---

## Qué no afirmar durante la presentación

> [!CAUTION]
> Las siguientes afirmaciones son **incorrectas** y no deben realizarse:

1. **No decir** que el sistema está en producción.
2. **No decir** que el sistema ya adapta OBS automáticamente.
3. **No decir** que el bitrate de OBS mide la capacidad disponible de la red.
4. **No decir** que los modelos ya fueron validados con datos reales.
5. **No decir** que una degradación fue detectada si no hubo evidencia documentada.
6. **No decir** que el generalization gap es aceptable para producción.
7. **No decir** que el modelo predictivo tiene alta confiabilidad (recall = 0.33).

## Qué sí se puede afirmar

1. Los modelos de la Fase 1 están entrenados, congelados y verificados.
2. La cadena de transmisión completa funciona (VDO.Ninja → OBS → MediaMTX).
3. El recolector de telemetría funciona y produce datos válidos.
4. Se obtuvo una primera sesión estable con 0 errores.
5. El sistema no toma decisiones automáticas actualmente.
6. El siguiente paso es activar Shadow Mode para comparar predicciones vs realidad.
