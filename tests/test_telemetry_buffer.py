import pytest
import pandas as pd
from datetime import datetime, timezone
from src.telemetry_buffer import TelemetryBuffer

def test_buffer_empty():
    buf = TelemetryBuffer(lookback_seconds=120, min_coverage=0.8)
    cov, n = buf.get_coverage()
    assert cov == 0.0
    assert n == 0
    assert not buf.is_ready()
    assert buf.get_dataframe().empty

def test_add_invalid_sample():
    buf = TelemetryBuffer()
    assert not buf.add_sample({"no_ts": 1})
    assert not buf.add_sample({"timestamp_utc": "invalid_date"})
    future_ts = (pd.Timestamp.utcnow() + pd.Timedelta(seconds=10)).isoformat()
    assert not buf.add_sample({"timestamp_utc": future_ts})

def test_buffer_coverage_and_window():
    buf = TelemetryBuffer(lookback_seconds=10, min_coverage=0.8)
    now = pd.Timestamp.utcnow()

    # Agregar 5 segundos de datos (cobertura 4s / 10s = 0.4)
    for i in range(5):
        ts = (now - pd.Timedelta(seconds=(20-i))).isoformat()
        buf.add_sample({"timestamp_utc": ts, "val": i, "observed_throughput_mbps": 5.0})

    cov, n = buf.get_coverage()
    assert cov == 0.4

    # Agregar 5 segundos mas (cobertura 9s / 10s = 0.9)
    for i in range(5, 10):
        ts = (now - pd.Timedelta(seconds=(20-i))).isoformat()
        buf.add_sample({"timestamp_utc": ts, "val": i, "observed_throughput_mbps": 5.0})

    cov, n = buf.get_coverage()
    assert cov == 0.9

    # Agregar 2 segundos mas, debería desplazar la ventana
    for i in range(10, 12):
        ts = (now - pd.Timedelta(seconds=(20-i))).isoformat()
        buf.add_sample({"timestamp_utc": ts, "val": i, "observed_throughput_mbps": 5.0})

    cov, n = buf.get_coverage()
    assert cov >= 0.8
    assert n == 10

def test_buffer_duplicates_and_order():
    buf = TelemetryBuffer()
    now = pd.Timestamp.utcnow()
    ts1 = now.isoformat()
    ts2 = (now - pd.Timedelta(seconds=1)).isoformat()
    
    buf.add_sample({"timestamp_utc": ts1, "v": 1, "observed_throughput_mbps": 5.0})
    buf.add_sample({"timestamp_utc": ts1, "v": 2, "observed_throughput_mbps": 5.0}) # duplicate
    buf.add_sample({"timestamp_utc": ts2, "v": 3, "observed_throughput_mbps": 5.0}) # out of order
    
    df = buf.get_dataframe()
    assert len(df) == 2
    # El orden debe ser ts2 primero luego ts1
    assert df.iloc[0]['timestamp_utc'] == ts2
    assert df.iloc[1]['timestamp_utc'] == ts1
