import pytest
from unittest.mock import patch, MagicMock
from src.obs_telemetry_collector import OBSTelemetryCollector

@pytest.fixture
def mock_collector():
    return OBSTelemetryCollector()

def test_connection_failed(mock_collector):
    with patch('obsws_python.ReqClient', side_effect=Exception("Failed")):
        assert not mock_collector.connect()
        metrics = mock_collector.get_metrics()
        assert metrics['obs_connected'] is False
        assert metrics['fps'] is None
        assert metrics['bitrate_kbps'] is None
        assert metrics['bitrate_status'] == 'inactive'

def test_bitrate_logic(mock_collector):
    mock_client = MagicMock()
    mock_stats = MagicMock()
    mock_client.get_stats.return_value = mock_stats
    
    mock_stream = MagicMock()
    mock_stream.output_active = True
    mock_stream.output_bytes = 1000000
    mock_client.get_stream_status.return_value = mock_stream
    
    with patch('obsws_python.ReqClient', return_value=mock_client), \
         patch('time.time', side_effect=[100.0, 101.0, 102.0, 103.0, 104.0, 105.0]):
         
        mock_collector.connect()
        
        # 1. Primera lectura: null (warmup)
        metrics1 = mock_collector.get_metrics()
        assert metrics1['bitrate_kbps'] is None
        assert metrics1['bitrate_status'] == 'warmup'
        
        # 2. Segunda lectura: calculo correcto
        mock_stream.output_bytes = 2000000 # 1MB diff in 1s = 8000 kbps
        metrics2 = mock_collector.get_metrics()
        assert metrics2['bitrate_kbps'] == 8000.0
        assert metrics2['bitrate_status'] == 'valid'
        
        # 3. Bytes reiniciados
        mock_stream.output_bytes = 500000 # smaller than 2M
        metrics3 = mock_collector.get_metrics()
        assert metrics3['bitrate_kbps'] is None
        assert metrics3['bitrate_status'] == 'reset'

def test_time_zero_and_inactive(mock_collector):
    mock_client = MagicMock()
    mock_stats = MagicMock()
    mock_client.get_stats.return_value = mock_stats
    
    mock_stream = MagicMock()
    mock_stream.output_active = True
    mock_stream.output_bytes = 1000000
    mock_client.get_stream_status.return_value = mock_stream
    
    with patch('obsws_python.ReqClient', return_value=mock_client), \
         patch('time.time', side_effect=[100.0, 100.0, 101.0]):
        mock_collector.connect()
        
        # Warmup
        mock_collector.get_metrics()
        
        # Tiempo cero
        mock_stream.output_bytes = 2000000
        m = mock_collector.get_metrics()
        assert m['bitrate_kbps'] is None
        assert m['bitrate_status'] == 'error'

        # Stream inactivo
        mock_stream.output_active = False
        m2 = mock_collector.get_metrics()
        assert m2['bitrate_kbps'] is None
        assert m2['bitrate_status'] == 'inactive'

def test_reconnection(mock_collector):
    mock_client = MagicMock()
    mock_stream = MagicMock()
    mock_stream.output_active = True
    mock_stream.output_bytes = 1000
    mock_client.get_stream_status.return_value = mock_stream
    
    with patch('obsws_python.ReqClient', return_value=mock_client):
        mock_collector.connect()
        
        m1 = mock_collector.get_metrics()
        assert m1['bitrate_status'] == 'warmup'
        
        # Simular reconexion
        mock_collector.connect()
        m2 = mock_collector.get_metrics()
        assert m2['bitrate_status'] == 'warmup' # Debe volver a ser warmup
