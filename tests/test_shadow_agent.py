import pytest
import pandas as pd
from datetime import datetime, timezone
from src.shadow_agent import ShadowAgent

@pytest.fixture
def agent():
    return ShadowAgent()

def test_invalid_samples(agent):
    res = agent.process_sample({})
    assert res['inference_status'] == 'invalid_sample'
    assert res['action_applied'] == 'none'
    
    # Missing variables
    res = agent.process_sample({
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'upload_mbps': 5.0
    })
    assert res['inference_status'] == 'invalid_sample'
    
    # Negative values
    res = agent.process_sample({
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'upload_mbps': -1.0,
        'download_mbps': 5.0,
        'latency_ms': 20.0
    })
    assert res['inference_status'] == 'invalid_sample'

def test_insufficient_network_capacity(agent):
    res = agent.process_sample({
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'upload_traffic_mbps': 5.0,
        'download_traffic_mbps': 50.0,
        'latency_ms': 10.0,
        'upload_mbps': None,
        'download_mbps': None
    })
    
    # Debe ser insufficient_network_capacity porque upload_mbps y download_mbps son null
    assert res['inference_status'] == 'insufficient_network_capacity'
    assert res['reactive_prediction'] is None
    assert res['action_applied'] == 'none'

def test_reactive_inference(agent):
    res = agent.process_sample({
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'upload_mbps': 5.0,
        'download_mbps': 50.0,
        'latency_ms': 10.0,
        'upload_traffic_mbps': 5.0 # Necesario para valid observed_throughput_mbps
    })
    
    assert res['inference_status'] == 'reactive_only'
    assert res['reactive_prediction'] in ['low', 'medium', 'high']
    assert res['action_applied'] == 'none'
    assert res['predictive_prediction'] is None
    assert res['recommendation'] == 'insufficient_buffer'

def test_throughput_priority(agent):
    # Test prioridad de bitrate_kbps
    res1 = agent.process_sample({
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'bitrate_kbps': 6000.0,
        'upload_traffic_mbps': 4.0
    })
    assert res1['observed_throughput_mbps'] == 6.0
    assert res1['predictive_input_source'] == 'unavailable'
    
    # Test fallback a upload_traffic_mbps
    res2 = agent.process_sample({
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'bitrate_kbps': None,
        'upload_traffic_mbps': 4.5
    })
    assert res2['observed_throughput_mbps'] == 4.5
    assert res2['predictive_input_source'] == 'unavailable'

    # Test unavailable
    res3 = agent.process_sample({
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'bitrate_kbps': -1,
        'upload_traffic_mbps': None
    })
    assert res3['observed_throughput_mbps'] is None
    assert res3['predictive_input_source'] == 'unavailable'

def test_predictive_activation_without_reactive(agent):
    # Simular > 96 segundos de cobertura usando upload_traffic_mbps sin upload_mbps
    now = pd.Timestamp.utcnow()
    
    for i in range(100):
        ts = (now - pd.Timedelta(seconds=(100-i))).isoformat()
        res = agent.process_sample({
            'timestamp_utc': ts,
            'upload_traffic_mbps': 5.0, # Datos válidos para el reactivo/buffer
            'predictive_throughput_mbps': 5.0, # Fuerza fuente compatible para el test
            'upload_mbps': None, # Invalida el reactivo
            'download_mbps': None,
            'latency_ms': 10.0
        })
        
    assert res['inference_status'] == 'full_inference'
    assert res['reactive_prediction'] is None # Sin reactivo
    assert res['action_applied'] == 'none'
    assert res['predictive_prediction'] in ['maintain', 'downgrade_needed']
    assert 0.0 <= res['degradation_probability'] <= 1.0
    assert res['recommendation'] in ['maintain', 'downgrade']

class MockModel:
    def __init__(self, classes_, proba_ret):
        self.classes_ = classes_
        self.proba_ret = proba_ret
    def predict_proba(self, X):
        return self.proba_ret

def test_resolve_downgrade_class_index(agent):
    # Clases numéricas [0, 1]
    assert agent.resolve_downgrade_class_index(MockModel([0, 1], None)) == 1
    
    # Clases numéricas invertidas [1, 0]
    assert agent.resolve_downgrade_class_index(MockModel([1, 0], None)) == 0
    
    # Clases de texto
    assert agent.resolve_downgrade_class_index(MockModel(['maintain', 'downgrade_needed'], None)) == 1
    
    # Clases de texto invertidas
    assert agent.resolve_downgrade_class_index(MockModel(['downgrade_needed', 'maintain'], None)) == 0
    
    # Clase positiva inexistente
    import pytest
    with pytest.raises(ValueError):
        agent.resolve_downgrade_class_index(MockModel(['maintain', 'other'], None))

def test_probability_validation(agent):
    # Forzamos buffer ready
    import pandas as pd
    from unittest.mock import patch
    import numpy as np
    
    agent.buffer.is_ready = lambda: True
    agent.buffer.get_dataframe = lambda: pd.DataFrame([{"_ts": pd.Timestamp.utcnow(), "observed_throughput_mbps": 5.0, "predictive_throughput_mbps": 5.0, "latency_ms": 10.0}])
    
    with patch('src.shadow_agent.build_predictive_features', return_value=pd.DataFrame([{"feat": 1}])):
        with patch.object(agent.predictive_prep, 'transform', return_value=[[1]]):
            valid_ts = pd.Timestamp.utcnow().isoformat()
            
            payload = {'timestamp_utc': valid_ts, 'upload_traffic_mbps': 5.0, 'predictive_throughput_mbps': 5.0, 'upload_mbps': None}

            # 1. predict_proba con forma incorrecta
            agent.predictive_model = MockModel([0, 1], [[0.5]]) # Faltan columnas
            res = agent.process_sample(payload)
            assert res['inference_status'] == 'error'
            assert res['degradation_probability'] is None
            
            # 2. probabilidad no finita
            agent.predictive_model = MockModel([0, 1], [[0.5, np.inf]])
            res = agent.process_sample(payload)
            assert res['inference_status'] == 'error'
            assert res['degradation_probability'] is None
            
            # 3. aplicación correcta del umbral 0.55
            agent.predictive_model = MockModel([0, 1], [[0.4, 0.6]]) # 0.6 > 0.55
            res = agent.process_sample(payload)
            assert res['inference_status'] == 'full_inference'
            assert res['predictive_prediction'] == 'downgrade_needed'
            assert res['degradation_probability'] == 0.6
            
            agent.predictive_model = MockModel([0, 1], [[0.6, 0.4]]) # 0.4 < 0.55
            res = agent.process_sample(payload)
            assert res['inference_status'] == 'full_inference'
            assert res['predictive_prediction'] == 'maintain'
            assert res['degradation_probability'] == 0.4
