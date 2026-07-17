# Dataset Card: reactive_dataset

## Fuente

- Dataset: RTR-NetzTest Open Data.
- Archivo usado: `data/raw/reactive/netztest-opendata_hours-048.csv`.
- SHA-256: `8f0b8ac6aa178026cca398e02cd3174488e7b33f5c8746939b88996ea0e05f6e`.
- Datos sinteticos: no.

## Semantica

Cada fila representa una medicion real de red. `open_test_uuid` se conserva como `session_id`
porque el dataset reactivo es puntual y no contiene ventanas temporales largas por prueba.

## Variables de entrada

- `upload_mbps` (Mbps): subida medida por RTR.
- `download_mbps` (Mbps): descarga medida por RTR.
- `latency_ms` (ms): latencia medida por RTR.

## Target

`target` es una pseudoetiqueta `low`, `medium` o `high`: Pseudo-label: high when upload >= 6.75 Mbps, medium when upload >= 3.375 Mbps, otherwise low; latency > 300 ms forces low and latency > 150 ms caps high to medium.

## Tamano y particiones

- Filas: 26686
- Sesiones: 26686
- Distribucion: {'high': 21590, 'low': 2798, 'medium': 2298}
- Filas por split: {'train': 16012, 'validation': 5337, 'test': 5337}
