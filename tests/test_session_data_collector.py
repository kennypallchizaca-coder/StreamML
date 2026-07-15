import pytest
import datetime
from unittest.mock import patch, MagicMock
from src.session_data_collector import SessionDataCollector

def test_session_data_collector_initialization():
    collector = SessionDataCollector()
    assert collector.session_id is not None
    assert collector.config['mode'] == 'collection_only'

def test_collect_sample():
    with patch('src.session_data_collector.OBSTelemetryCollector.get_metrics') as mock_tel:
        mock_tel.return_value = {
            'timestamp_utc': '2026-07-14T10:00:00Z',
            'obs_connected': True,
            'stream_active': True,
            'bitrate_kbps': 6000.0,
            'fps': 60.0,
            'dropped_frames': 0,
            'total_frames': 1000,
            'output_congestion': 0.0,
            'output_reconnecting': False,
            'upload_traffic_mbps': 6.5,
            'download_traffic_mbps': 0.1,
            'latency_ms': 15.0,
            'network_status': 'connected'
        }
        
        collector = SessionDataCollector()
        collector.start_time = datetime.datetime.now(datetime.timezone.utc)
        
        sample = collector.collect_sample(profile_name='high', condition='stable')
        
        assert sample['session_id'] == collector.session_id
        assert sample['current_profile_name'] == 'high'
        assert sample['current_profile_code'] == 3
        assert sample['required_capacity_mbps'] == 6.75
        assert sample['experimental_condition'] == 'stable'
        assert sample['event_label'] == 'stable'
        assert sample['action_applied'] == 'none'
        assert sample['obs_bitrate_kbps'] == 6000.0
        assert sample['network_traffic_upload_mbps'] == 6.5
        assert 'predictive_throughput_mbps' not in sample # Ensure we don't accidentally generate it here
