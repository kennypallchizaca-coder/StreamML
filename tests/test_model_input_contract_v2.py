import pytest
import pandas as pd
import numpy as np
import joblib
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.feature_builder_v2 import build_predictive_features

def test_reactive_contract():
    # 1. Fila realista se puede convertir al contrato (usamos un dict de telemetria)
    telemetry = {
        'upload_mbps': 5.5,
        'download_mbps': 20.0,
        'latency_ms': 45.0,
        'network_type': 'should_be_ignored',
        'cat_technology': 'should_be_ignored',
        'signal_strength': 'should_be_ignored'
    }
    df = pd.DataFrame([telemetry])
    
    # Comprobar que ping_ms no se usa
    assert 'ping_ms' not in df.columns
    # Extraemos solo lo necesario
    df_req = df[['upload_mbps', 'download_mbps', 'latency_ms']]
    assert df_req.shape[1] == 3

def test_predictive_buffer():
    # Crear un historial falso de 120 segundos
    data = []
    for i in range(120):
        data.append({'timestamp_utc': i, 'upload_mbps': 5.0 + np.sin(i)})
    df = pd.DataFrame(data)
    
    # Probar construir
    res = build_predictive_features(df)
    assert res.shape == (1, 19)
    assert res['measurements_count'].iloc[0] == 120
    assert 'throughput_mean' in res.columns
    
def test_insufficient_buffer():
    # Ventana insuficiente falla
    df = pd.DataFrame({'timestamp_utc': [1,2], 'upload_mbps': [5.0, 5.0]})
    with pytest.raises(ValueError, match="Cobertura insuficiente"):
        build_predictive_features(df)
        
def test_negative_values():
    df = pd.DataFrame({'timestamp_utc': range(120), 'upload_mbps': [-5.0] * 120})
    with pytest.raises(ValueError, match="Valores negativos"):
        build_predictive_features(df)

def test_missing_columns():
    df = pd.DataFrame({'timestamp_utc': range(120), 'otro': [5.0] * 120})
    with pytest.raises(ValueError, match="No se puede calcular"):
        build_predictive_features(df)

def test_model_loading_and_reproducibility():
    mod_r = joblib.load('models/modelo_reactivo_shadow_v2.joblib')
    prep_r = joblib.load('models/preprocesador_reactivo_shadow_v2.joblib')
    
    df = pd.DataFrame([{'upload_mbps': 5.5, 'download_mbps': 20.0, 'latency_ms': 45.0}])
    X = prep_r.transform(df)
    p1 = mod_r.predict(X)
    p2 = mod_r.predict(X)
    assert np.array_equal(p1, p2)
    
    mod_p = joblib.load('models/modelo_predictivo_shadow_v2.joblib')
    prep_p = joblib.load('models/preprocesador_predictivo_shadow_v2.joblib')
    
    data = []
    for i in range(120): data.append({'timestamp_utc': i, 'upload_mbps': 5.0})
    feat = build_predictive_features(pd.DataFrame(data))
    X_p = prep_p.transform(feat)
    pp1 = mod_p.predict(X_p)
    pp2 = mod_p.predict(X_p)
    assert np.array_equal(pp1, pp2)
