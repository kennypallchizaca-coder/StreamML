# Dataset Card: predictive_dataset

## Fuente

- Dataset: YouTube Dataset on Mobile Streaming for Internet Traffic Modeling, Network Management, and Streaming Analysis
- DOI dataset: 10.6084/m9.figshare.19096823.v2
- Licencia: CC BY 4.0
- URL: https://figshare.com/articles/dataset/YouTube_Dataset_on_Mobile_Streaming_for_Internet_Traffic_Modeling_Network_Management_and_Streaming_Analysis/19096823
- Datos sinteticos: no.

## Semantica

Cada fila representa una ventana historica de 120 segundos de una unica sesion del dataset publico,
con una etiqueta calculada usando los 30 segundos estrictamente futuros.

## Variables de entrada

Las 19 variables se definen en `config/predictive_feature_contract.json`. Las columnas
`future_*`, `target` y `target_code` no se usan como features.

## Target

`downgrade_needed` cuando el horizonte futuro contiene rebuffering, bajada de calidad, p25 por debajo
de la capacidad requerida o mas de 30% de muestras futuras bajo esa capacidad.

## Tamano

- Sesiones: 120
- Ventanas: 3306
- Distribucion: {'downgrade_needed': 2864, 'maintain': 442}
