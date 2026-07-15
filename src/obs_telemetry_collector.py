import os
import time
import obsws_python as obs
from dotenv import load_dotenv

class OBSTelemetryCollector:
    def __init__(self, config=None):
        load_dotenv()
        
        self.host = os.environ.get('OBS_WEBSOCKET_HOST', '127.0.0.1')
        self.port = os.environ.get('OBS_WEBSOCKET_PORT', '4455')
        self.password = os.environ.get('OBS_WEBSOCKET_PASSWORD', '')
        
        self.config = config or {}
        self.read_only = self.config.get('obs_read_only', True)
        self.timeout = self.config.get('obs_connection_timeout_seconds', 5)
        
        self.client = None
        self._last_bytes = 0
        self._last_time = None
        self._first_reading = True

    def connect(self):
        try:
            self.client = obs.ReqClient(
                host=self.host, 
                port=self.port, 
                password=self.password,
                timeout=self.timeout
            )
            self._first_reading = True
            return True
        except Exception as e:
            self.client = None
            return False

    def is_connected(self):
        return self.client is not None

    def get_metrics(self):
        """Obtiene métricas de OBS usando solo llamadas de lectura."""
        result = {
            "obs_connected": False,
            "fps": None,
            "dropped_frames": None,
            "total_frames": None,
            "bitrate_kbps": None,
            "output_active": False,
            "bitrate_status": "inactive"
        }
        
        if not self.is_connected():
            if not self.connect():
                result["bitrate_status"] = "inactive"
                return result
                
        try:
            stats = self.client.get_stats()
            
            result["fps"] = getattr(stats, 'active_fps', None)
            result["dropped_frames"] = getattr(stats, 'output_skipped_frames', None)
            result["total_frames"] = getattr(stats, 'output_total_frames', None)
            
            stream_status = self.client.get_stream_status()
            active = getattr(stream_status, 'output_active', False)
            result["output_active"] = active
            
            current_time = time.time()
            if active:
                current_bytes = getattr(stream_status, 'output_bytes', 0)
                
                if self._first_reading or self._last_time is None:
                    result["bitrate_kbps"] = None
                    result["bitrate_status"] = "warmup"
                    self._last_bytes = current_bytes
                    self._last_time = current_time
                    self._first_reading = False
                else:
                    time_diff = current_time - self._last_time
                    byte_diff = current_bytes - self._last_bytes
                    
                    if current_bytes < self._last_bytes:
                        # Reset
                        result["bitrate_kbps"] = None
                        result["bitrate_status"] = "reset"
                        self._last_bytes = current_bytes
                        self._last_time = current_time
                    elif time_diff <= 0:
                        result["bitrate_kbps"] = None
                        result["bitrate_status"] = "error"
                        self._last_bytes = current_bytes
                        self._last_time = current_time
                    else:
                        bitrate_kbps = (byte_diff * 8) / time_diff / 1000.0
                        result["bitrate_kbps"] = round(bitrate_kbps, 3)
                        result["bitrate_status"] = "valid"
                        self._last_bytes = current_bytes
                        self._last_time = current_time
            else:
                self._last_bytes = 0
                self._last_time = None
                self._first_reading = True
                result["bitrate_kbps"] = None
                result["bitrate_status"] = "inactive"
                
            result["obs_connected"] = True
            
        except Exception as e:
            self.client = None
            result["obs_connected"] = False
            result["bitrate_status"] = "error"
            self._first_reading = True
            
        return result
