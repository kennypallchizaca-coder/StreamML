# StreamML online-only cleanup

Fecha: 2026-07-17

## Alcance y respaldo

- Se creó y verificó el respaldo externo `../backups/Adaptive-Streaming-ai_online_only_20260717_022135` antes de eliminar archivos.
- Proyecto y respaldo coincidieron: 3.083 archivos y 134.911.714 bytes.
- No se reentrenaron modelos ni se cambiaron métricas, features, clases o threshold.
- No se eliminaron datasets originales, datasets procesados oficiales, notebooks ni modelos oficiales.
- No se realizó commit ni push.

## Línea base

- `pytest -v`: 42 pruebas aprobadas.
- `python scripts/verify_release.py`: `STREAMML RELEASE VERIFIED`.
- `python scripts/demo_models.py`: `STREAMML DEMO COMPLETED`.

## Archivos eliminados

| Archivo o directorio | Motivo |
|---|---|
| `apps/offline_gui/app.py` | Interfaz Streamlit heredada; el producto utiliza únicamente React. |
| `apps/offline_gui/__init__.py` | Paquete exclusivo de la interfaz eliminada. |
| `src/streamml/features/dataframe_validation.py` | Helper consumido únicamente por Streamlit y sus pruebas. |
| `src/streamml/inference/offline.py` | Servicio de inferencia exclusivo de Streamlit, reemplazado por el motor estricto de la API. |
| `src/streamml/inference/offline_loader.py` | Cargador exclusivo de Streamlit, reemplazado por `OfficialModelRegistry`. |
| `tests/unit/test_offline_inference.py` | Seis pruebas exclusivas del código anterior eliminado. |
| `models/registry/reactive/model_metadata.json` | Resumen redundante no versionado, no incluido en el release oficial y usado solo por Streamlit. |
| `models/registry/predictive/model_metadata.json` | Resumen redundante no versionado, no incluido en el release oficial y usado solo por Streamlit. |
| `data/samples/` | Directorio vacío sin referencias ni muestras reales. |
| `pipelines/` | Responsabilidad duplicada con `scripts/`; la implementación fue consolidada. |
| `__pycache__/`, `*.pyc`, `.pytest_cache/` | Cachés reconstruibles. |
| `apps/frontend/dist/` | Build reconstruible, retirado después de validar `npm run build`. |

También se retiró `streamlit` de `requirements.txt` y se eliminó la generación futura de los dos `model_metadata.json` redundantes.

## Archivos movidos o consolidados

- `pipelines/prepare_datasets.py` → `scripts/prepare_datasets.py`.
- `pipelines/train_models.py` → `scripts/train_models.py`.
- `pipelines/evaluate_models.py` → `scripts/evaluate_models.py`.
- Los wrappers delgados que ocupaban esos tres destinos fueron sustituidos por la implementación real.
- `scripts/` es ahora el único directorio de comandos de preparación, entrenamiento, evaluación, demo y verificación.

## Duplicados exactos conservados

| Grupo | Copias | Motivo |
|---|---:|---|
| `source_manifest.json` | 3 | La fuente canónica y una copia autocontenida por cada modelo oficial. |
| Contrato reactivo | 2 | Configuración de entrenamiento y copia inmutable junto al modelo publicado. |
| Contrato predictivo | 2 | Configuración de entrenamiento y copia inmutable junto al modelo publicado. |

Estas copias forman parte de la publicación verificable y no se eliminaron. Los campos históricos `offline_*` dentro de contratos, métricas y manifiestos oficiales también se conservaron para no modificar artefactos protegidos ni sus hashes. `GET /api/v1/models` los filtra y una prueba impide que aparezcan en la respuesta al cliente.

## Estructura final

```text
apps/
  api/
  connector/
  frontend/
data/
  raw/
  interim/
  processed/
deployment/
docs/
infrastructure/
models/
  registry/
notebooks/
  01_data_preparation.ipynb
  02_model_training.ipynb
  03_model_inference.ipynb
reports/
scripts/
src/
  streamml/
    config/
    data/
    domain/
    features/
    inference/
    observability/
    security/
    services/
    training/
tests/
  api/
  end_to_end/
  integration/
  models/
  unit/
```

## Modelos y notebooks

| Modelo | SHA-256 antes | SHA-256 después |
|---|---|---|
| Reactivo | `71c19fe0f350179fb381f6f71acad1612ccaab8563c638d174896e84a8acfa37` | `71c19fe0f350179fb381f6f71acad1612ccaab8563c638d174896e84a8acfa37` |
| Predictivo | `1f1c5ede45847252df85cc0c5a595677a2db663ff86d3535165bf4da704e24ec` | `1f1c5ede45847252df85cc0c5a595677a2db663ff86d3535165bf4da704e24ec` |

- Los tres notebooks son documentos v4 válidos y todas sus celdas de código conservan ejecución registrada.
- No se reejecutó entrenamiento.

## Validación final

- `pytest --collect-only -q`: 37 pruebas recopiladas.
- `pytest -v`: 37 aprobadas; una advertencia de deprecación de Starlette.
- `python -m compileall apps src scripts`: correcto.
- `python scripts/verify_release.py`: correcto.
- `python scripts/demo_models.py`: correcto.
- Importación de API, conector y registro oficial: correcta.
- Catálogo público de modelos: sin metadata de la superficie heredada.
- `npm run build`: correcto; Vite advierte que un chunk supera 500 kB.
- `docker compose ... config --quiet`: correcto.
- Pruebas físicas con teléfono, OBS y MediaMTX: pendientes; no se declara producción lista.

## Decisión

`PROJECT CLEAN AND ORGANIZED` para la superficie online; la validación física de streaming continúa pendiente.
