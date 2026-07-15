import os
import json
import uuid
import datetime
from typing import Dict, Any
from src.obs_telemetry_collector import OBSTelemetryCollector

PROFILE_MAPPING = {
    'low': {'code': 1, 'capacity': 1.35},
    'medium': {'code': 2, 'capacity': 3.375},
    'high': {'code': 3, 'capacity': 6.75}
}

class SessionDataCollector:
    def __init__(self, config_path='config/data_collection_config.json'):
        # OBSTelemetryCollector uses config dictionary
        self.obs_collector = OBSTelemetryCollector(config={
            'ws_host': os.environ.get('OBS_WEBSOCKET_HOST', 'localhost'),
            'ws_port': int(os.environ.get('OBS_WEBSOCKET_PORT', '4455')),
            'ws_password': os.environ.get('OBS_WEBSOCKET_PASSWORD', '')
        })
        self.session_id = str(uuid.uuid4())
        self.start_time = None
        self.config = self._load_config(config_path)

    def _load_config(self, path):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "mode": "collection_only",
            "action_applied": "none",
            "schema_version": "2.0"
        }

    def connect(self):
        self.obs_collector.connect()
        self.start_time = datetime.datetime.now(datetime.timezone.utc)

    def disconnect(self):
        pass

    def collect_sample(self, profile_name: str, condition: str) -> Dict[str, Any]:
        """Recolecta una muestra de telemetría y le añade los campos requeridos para la Fase 2."""
        raw_telemetry = self.obs_collector.get_metrics()
        
        now = datetime.datetime.now(datetime.timezone.utc)
        timestamp_utc = now.isoformat()
        if not timestamp_utc:
            # According to rules, return None to signal skipping the row
            return None
            
        elapsed = (now - self.start_time).total_seconds() if self.start_time else 0.0
        
        # Mapeo de perfil
        profile_info = PROFILE_MAPPING.get(profile_name.lower(), PROFILE_MAPPING['high'])
        
        sample = {
            'schema_version': self.config.get('schema_version', '2.0'),
            'session_id': self.session_id,
            'timestamp_utc': timestamp_utc,
            'elapsed_seconds': elapsed,
            'obs_connected': raw_telemetry.get('obs_connected', False),
            'stream_active': raw_telemetry.get('output_active', False),
            'obs_bitrate_kbps': raw_telemetry.get('bitrate_kbps'),
            'bitrate_status': raw_telemetry.get('bitrate_status', 'error'),
            'fps': raw_telemetry.get('fps'),
            'dropped_frames': raw_telemetry.get('dropped_frames', 0),
            'total_frames': raw_telemetry.get('total_frames', 0),
            'output_congestion': raw_telemetry.get('output_congestion', 0.0),
            'output_reconnecting': raw_telemetry.get('output_reconnecting', False),
            'network_traffic_upload_mbps': raw_telemetry.get('upload_traffic_mbps', 0.0),
            'network_traffic_download_mbps': raw_telemetry.get('download_traffic_mbps', 0.0),
            'latency_ms': raw_telemetry.get('latency_ms', 0.0),
            'network_status': raw_telemetry.get('network_status', 'unknown'),
            'current_profile_name': profile_name,
            'current_profile_code': profile_info['code'],
            'required_capacity_mbps': profile_info['capacity'],
            'experimental_condition': condition,
            'event_label': 'stable', # Por defecto
            'action_applied': self.config.get('action_applied', 'none')
        }
        
        return sample
