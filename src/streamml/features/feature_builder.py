import pandas as pd

from src.streamml.features.predictive_features import FEATURE_COLUMNS, build_feature_row

def build_predictive_features(
    historical_window: pd.DataFrame,
    current_profile: int = None,
    configuration: dict = None
) -> pd.DataFrame:
    """
    Construye las variables predictivas a partir de una ventana historica de 120 segundos.
    
    Espera un DataFrame con al menos:
    - timestamp_utc (o similar para ordenar)
    - throughput_mbps (si no existe, se calcula desde upload_mbps)
    """
    # 1. Validaciones iniciales
    if historical_window is None or historical_window.empty:
        raise ValueError("La ventana historica esta vacia.")
        
    df = historical_window.copy()
    
    if 'throughput_mbps' not in df.columns:
        if 'upload_mbps' in df.columns:
            df['throughput_mbps'] = df['upload_mbps']
        else:
            raise ValueError("No se puede calcular throughput_mbps. Se necesita una fuente compatible.")
            
    # Ordenar y limpiar
    timestamp_col = 'timestamp_utc' if 'timestamp_utc' in df.columns else '_ts' if '_ts' in df.columns else None
    if timestamp_col:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col], utc=True, errors='coerce')
        df = df.dropna(subset=[timestamp_col]).sort_values(timestamp_col).drop_duplicates(timestamp_col)
        
    # Validar negativos
    if (df['throughput_mbps'] < 0).any():
        raise ValueError("Valores negativos en throughput_mbps.")
        
    # Configuraciones
    lookback = 120
    min_coverage = 0.80
    if configuration:
        lookback = configuration.get('lookback_seconds', 120)
        min_coverage = configuration.get('minimum_coverage', 0.80)
        
    if len(df) < (lookback * min_coverage):
        raise ValueError("Cobertura insuficiente en la ventana historica.")
        
    # Limitar a los últimos 'lookback' segundos (asumiendo 1 fila por segundo aprox para el check)
    df = df.tail(lookback)
    
    if current_profile is None:
        p10 = df['throughput_mbps'].quantile(0.10)
        if p10 >= 6.75:
            current_profile = 3
        elif p10 >= 3.375:
            current_profile = 2
        else:
            current_profile = 1

    if timestamp_col:
        start = df[timestamp_col].iloc[0]
        elapsed = (df[timestamp_col] - start).dt.total_seconds().to_numpy(dtype=float)
    else:
        elapsed = list(range(len(df)))

    row = build_feature_row(
        df['throughput_mbps'].to_numpy(dtype=float),
        elapsed,
        int(current_profile),
        lookback_duration_seconds=float(lookback),
    )
    res = pd.DataFrame([row])
    return res[FEATURE_COLUMNS]
