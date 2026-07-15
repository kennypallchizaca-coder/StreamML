import json
import time
import uuid
import psutil
import subprocess
import socket
import csv
from datetime import datetime, timezone
from pathlib import Path
import os
from src.obs_telemetry_collector import OBSTelemetryCollector

class TelemetryCollector:
    def __init__(self, config_path="config/shadow_agent_config.json", schema_path="config/telemetry_schema.json"):
        self.config_path = Path(config_path)
        self.schema_path = Path(schema_path)
        
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                self.schema = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON configuration: {e}")

        self.session_id = str(uuid.uuid4())
        self.output_dir = Path(self.config.get("telemetry_output_directory", "data/telemetry"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_file = self.output_dir / f"{self.session_id}.csv"
        
        self.latency_host = self.config.get("latency_test_host", "8.8.8.8")
        self.sample_interval = self.config.get("sampling_interval_seconds", 1.0)
        self.release_version = self.config.get("models_info", {}).get("release_version", "unknown")
        self.schema_version = self.schema.get("schema_version", "1.0")
        
        self.fields = [f["name"] for f in self.schema.get("fields", [])]
        
        # Estado previo de red
        self._last_net_io = psutil.net_io_counters()
        self._last_time = time.time()
        
        # Iniciar colector OBS
        self.obs_collector = None
        if self.config.get("obs_websocket_enabled", False):
            self.obs_collector = OBSTelemetryCollector(config=self.config)
        
        # Crear archivo con encabezados
        self._init_csv()

    def _init_csv(self):
        try:
            with open(self.output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.fields)
                writer.writeheader()
        except IOError as e:
            raise IOError(f"Could not write to {self.output_file}: {e}")

    def measure_latency(self):
        """Mide la latencia haciendo ping al host configurado."""
        try:
            cmd = ['ping', '-n', '1', '-w', '1000', self.latency_host] if os.name == 'nt' else ['ping', '-c', '1', '-W', '1', self.latency_host]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            
            if result.returncode == 0:
                output = result.stdout.lower()
                if 'time=' in output or 'tiempo=' in output:
                    for part in output.split():
                        if part.startswith('time=') or part.startswith('tiempo='):
                            ms_str = part.split('=')[1].replace('ms', '').strip()
                            if ms_str.startswith('<'):
                                return 1.0
                            return float(ms_str)
            return None
        except Exception:
            return None

    def _check_real_connectivity(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            result = sock.connect_ex(('8.8.8.8', 53))
            sock.close()
            return result == 0
        except Exception:
            return False

    def measure_network(self):
        current_net_io = psutil.net_io_counters()
        current_time = time.time()
        
        time_diff = current_time - self._last_time
        if time_diff <= 0:
            time_diff = 0.0001
            
        bytes_sent = current_net_io.bytes_sent - self._last_net_io.bytes_sent
        bytes_recv = current_net_io.bytes_recv - self._last_net_io.bytes_recv
        
        upload_mbps = (bytes_sent * 8) / (1_000_000 * time_diff)
        download_mbps = (bytes_recv * 8) / (1_000_000 * time_diff)
        
        self._last_net_io = current_net_io
        self._last_time = current_time
        
        return round(upload_mbps, 3), round(download_mbps, 3)

    def collect_sample(self):
        upload_traffic_mbps, download_traffic_mbps = self.measure_network()
        latency_ms = self.measure_latency()
        
        if latency_ms is not None:
            network_status = "connected" if latency_ms <= 150 else "degraded"
        else:
            if self._check_real_connectivity():
                network_status = "unknown"
            else:
                network_status = "disconnected"
            
        obs_metrics = {
            "obs_connected": False,
            "fps": None,
            "dropped_frames": None,
            "total_frames": None,
            "bitrate_kbps": None,
            "output_active": False
        }
        
        if self.obs_collector:
            obs_metrics = self.obs_collector.get_metrics()
            
        row = {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "sample_interval_seconds": self.sample_interval,
            "upload_traffic_mbps": upload_traffic_mbps,
            "upload_mbps": None,
            "download_traffic_mbps": download_traffic_mbps,
            "download_mbps": None,
            "latency_ms": latency_ms,
            "bitrate_kbps": obs_metrics.get("bitrate_kbps"),
            "fps": obs_metrics.get("fps"),
            "dropped_frames": obs_metrics.get("dropped_frames"),
            "total_frames": obs_metrics.get("total_frames"),
            "network_status": network_status,
            "obs_connected": obs_metrics.get("obs_connected", False),
            "current_profile": None,
            "reactive_prediction": None,
            "predictive_prediction": None,
            "degradation_probability": None,
            "recommendation": None,
            "action_applied": "none",
            "model_release_version": self.release_version
        }
        
        filtered_row = {k: row.get(k) for k in self.fields}
        
        try:
            with open(self.output_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.fields)
                writer.writerow(filtered_row)
            return filtered_row
        except IOError:
            return None
