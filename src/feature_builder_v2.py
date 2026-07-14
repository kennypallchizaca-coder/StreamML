import pandas as pd
import numpy as np

def build_predictive_features(
    telemetry_window: pd.DataFrame,
    current_profile: int = None,
    configuration: dict = None
) -> pd.DataFrame:
    """
    Construye las variables predictivas a partir de una ventana de telemetría (120s).
    
    Espera un DataFrame con al menos:
    - timestamp_utc (o similar para ordenar)
    - throughput_mbps (si no existe, se calcula desde upload_mbps)
    """
    # 1. Validaciones iniciales
    if telemetry_window is None or telemetry_window.empty:
        raise ValueError("La ventana de telemetría está vacía.")
        
    df = telemetry_window.copy()
    
    if 'throughput_mbps' not in df.columns:
        if 'upload_mbps' in df.columns:
            df['throughput_mbps'] = df['upload_mbps']
        elif 'bitrate_kbps' in df.columns:
            df['throughput_mbps'] = df['bitrate_kbps'] / 1000.0
        else:
            raise ValueError("No se puede calcular throughput_mbps. Se necesita upload_mbps o bitrate_kbps.")
            
    # Ordenar y limpiar
    if 'timestamp_utc' in df.columns:
        df = df.sort_values('timestamp_utc').drop_duplicates()
        
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
        raise ValueError("Cobertura insuficiente en la ventana de telemetría.")
        
    # Limitar a los últimos 'lookback' segundos (asumiendo 1 fila por segundo aprox para el check)
    df = df.tail(lookback)
    
    # Cálculos
    th = df['throughput_mbps']
    
    feat = {}
    feat['throughput_mean'] = th.mean()
    feat['throughput_median'] = th.median()
    feat['throughput_min'] = th.min()
    feat['throughput_max'] = th.max()
    feat['throughput_std'] = th.std()
    feat['throughput_p10'] = th.quantile(0.10)
    feat['throughput_p25'] = th.quantile(0.25)
    feat['throughput_first'] = th.iloc[0]
    feat['throughput_last'] = th.iloc[-1]
    feat['throughput_change'] = th.iloc[-1] - th.iloc[0]
    
    x = np.arange(len(th))
    feat['throughput_slope'] = np.polyfit(x, th, 1)[0] if len(th) > 1 else 0.0
    feat['throughput_coefficient_variation'] = (feat['throughput_std'] / feat['throughput_mean']) if feat['throughput_mean'] > 0 else 0
    feat['measurements_count'] = len(th)
    feat['lookback_duration_seconds'] = lookback
    
    # Proporciones
    feat['proportion_below_low'] = (th < 1.35).mean()
    feat['proportion_below_medium'] = (th < 3.375).mean()
    feat['proportion_below_high'] = (th < 6.75).mean()
    
    # Profile y Capacity
    PROFILE_CAPACITY = {1: 1.35, 2: 3.375, 3: 6.75} # 1: low, 2: medium, 3: high
    
    if current_profile is None:
        if feat['throughput_p10'] >= 6.75:
            current_profile = 3
        elif feat['throughput_p10'] >= 3.375:
            current_profile = 2
        else:
            current_profile = 1
            
    feat['current_profile'] = current_profile
    feat['required_capacity_mbps'] = PROFILE_CAPACITY.get(current_profile, 3.375)
    
    # Asegurar el orden de columnas esperado por el modelo
    EXPECTED_COLS = [
        'throughput_mean', 'throughput_median', 'throughput_min', 'throughput_max', 
        'throughput_std', 'throughput_p10', 'throughput_p25', 'throughput_first', 
        'throughput_last', 'throughput_change', 'throughput_slope', 'throughput_coefficient_variation', 
        'measurements_count', 'lookback_duration_seconds', 'proportion_below_low', 
        'proportion_below_medium', 'proportion_below_high', 'current_profile', 'required_capacity_mbps'
    ]
    
    res = pd.DataFrame([feat])
    return res[EXPECTED_COLS]
