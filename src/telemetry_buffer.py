import pandas as pd
from datetime import datetime

class TelemetryBuffer:
    def __init__(self, lookback_seconds: int = 120, min_coverage: float = 0.8):
        self.lookback_seconds = lookback_seconds
        self.min_coverage = min_coverage
        self.buffer = []

    def add_sample(self, sample: dict):
        """Añade una muestra al buffer si tiene datos validos y actualiza la ventana."""
        if 'timestamp_utc' not in sample:
            return False
            
        throughput = sample.get('observed_throughput_mbps')
        if throughput is None or throughput < 0:
            return False
            
        try:
            ts = pd.to_datetime(sample['timestamp_utc'])
        except (ValueError, TypeError):
            return False

        # Rechazar futuros (mas de 5 segundos en el futuro para tolerancia)
        if ts > pd.Timestamp.utcnow() + pd.Timedelta(seconds=5):
            return False

        # Guardar en buffer temporal (incluir ts parseado para ordenar)
        row = sample.copy()
        row['_ts'] = ts
        self.buffer.append(row)
        
        # Eliminar duplicados y ordenar
        self._clean_buffer()
        return True

    def _clean_buffer(self):
        if not self.buffer:
            return
            
        # Ordenar por tiempo
        self.buffer.sort(key=lambda x: x['_ts'])
        
        # Eliminar duplicados de timestamp
        unique_buffer = []
        seen_ts = set()
        for row in self.buffer:
            if row['_ts'] not in seen_ts:
                seen_ts.add(row['_ts'])
                unique_buffer.append(row)
        
        self.buffer = unique_buffer
        
        # Mantener solo ventana
        latest_ts = self.buffer[-1]['_ts']
        cutoff_ts = latest_ts - pd.Timedelta(seconds=self.lookback_seconds)
        
        self.buffer = [row for row in self.buffer if row['_ts'] > cutoff_ts]

    def get_coverage(self):
        """Retorna la cobertura del buffer [0, 1] y cantidad de medidas."""
        if not self.buffer:
            return 0.0, 0
            
        latest_ts = self.buffer[-1]['_ts']
        oldest_ts = self.buffer[0]['_ts']
        
        duration = (latest_ts - oldest_ts).total_seconds()
        
        # Cobertura sobre lookback_seconds
        coverage = min(1.0, duration / self.lookback_seconds)
        return coverage, len(self.buffer)

    def is_ready(self):
        """Retorna True si el buffer alcanza la cobertura mínima."""
        coverage, _ = self.get_coverage()
        return coverage >= self.min_coverage

    def get_dataframe(self):
        """Devuelve un DataFrame limpio sin la columna _ts, apto para inferencia."""
        if not self.buffer:
            return pd.DataFrame()
        df = pd.DataFrame(self.buffer)
        df = df.drop(columns=['_ts'])
        return df
