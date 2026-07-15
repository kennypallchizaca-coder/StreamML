import pytest
import csv
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.telemetry_collector import TelemetryCollector

@pytest.fixture
def mock_collector():
    return TelemetryCollector()

def test_session_id_generation(mock_collector):
    assert mock_collector.session_id is not None
    assert isinstance(mock_collector.session_id, str)
    assert len(mock_collector.session_id) > 10

def test_mbps_calculation(mock_collector):
    with patch('time.time') as mock_time, \
         patch('psutil.net_io_counters') as mock_net:
        
        mock_net.return_value = MagicMock(bytes_sent=0, bytes_recv=0)
        mock_time.return_value = 100.0
        mock_collector.measure_network()
        
        mock_time.return_value = 101.0
        mock_net.return_value = MagicMock(bytes_sent=1_000_000, bytes_recv=1_000_000)
        
        upload_mbps, download_mbps = mock_collector.measure_network()
        assert upload_mbps == 8.0
        assert download_mbps == 8.0

@patch('src.obs_telemetry_collector.OBSTelemetryCollector.get_metrics', return_value={'obs_connected': False, 'fps': None, 'dropped_frames': None, 'total_frames': None, 'bitrate_kbps': None, 'output_active': False})
@patch('src.telemetry_collector.TelemetryCollector.measure_network')
@patch('src.telemetry_collector.TelemetryCollector.measure_latency')
def test_csv_creation_and_order(mock_latency, mock_network, mock_obs, mock_collector):
    mock_network.return_value = (10.0, 50.0)
    mock_latency.return_value = 25.0
    
    mock_collector.collect_sample()
    
    assert mock_collector.output_file.exists()
    
    with open(mock_collector.output_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        
        assert headers == mock_collector.fields
        
        row = next(reader)
        
        assert row['session_id'] == mock_collector.session_id
        assert float(row['upload_traffic_mbps']) == 10.0
        assert row['upload_mbps'] == '' # null
        assert float(row['download_traffic_mbps']) == 50.0
        assert row['download_mbps'] == '' # null
        assert float(row['latency_ms']) == 25.0
        assert row['network_status'] == 'connected'
        assert row['obs_connected'] == 'False'
        assert row['bitrate_kbps'] == ''
        assert row['action_applied'] == 'none'
        assert row['reactive_prediction'] == ''

def test_missing_config():
    with pytest.raises(FileNotFoundError):
        TelemetryCollector(config_path="ruta_falsa.json")

def test_invalid_json(tmp_path):
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{ broken json")
    with pytest.raises(ValueError):
        TelemetryCollector(config_path=invalid_file)

@patch('src.telemetry_collector.TelemetryCollector._check_real_connectivity')
@patch('src.telemetry_collector.TelemetryCollector.measure_latency')
@patch('src.telemetry_collector.TelemetryCollector.measure_network')
def test_network_connectivity_logic(mock_network, mock_latency, mock_real_conn, mock_collector):
    mock_network.return_value = (10.0, 50.0)
    
    # Simular fallo de ping pero socket exitoso
    mock_latency.return_value = None
    mock_real_conn.return_value = True
    mock_collector.collect_sample()
    
    with open(mock_collector.output_file, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
        assert rows[-1]['network_status'] == 'unknown'
        
    # Simular fallo total
    mock_latency.return_value = None
    mock_real_conn.return_value = False
    mock_collector.collect_sample()
    
    with open(mock_collector.output_file, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
        assert rows[-1]['network_status'] == 'disconnected'
