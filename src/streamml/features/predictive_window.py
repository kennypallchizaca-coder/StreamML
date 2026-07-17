"""Build the immutable predictive input from the configured historical window."""

from __future__ import annotations

import math
from typing import Any

from src.streamml.features.predictive_features import build_feature_row

from src.streamml.domain.contracts import PREDICTIVE_COMPATIBLE_SOURCE
from .validation import IncompatibleFeatures, validate_generated_features


def build_predictive_features(
    samples: list[dict[str, Any]], current_profile: Any, contract: dict[str, Any]
) -> dict[str, float | int]:
    required_count = int(contract["lookback_seconds"])
    if len(samples) != required_count:
        raise IncompatibleFeatures([f"se requieren exactamente {required_count} muestras a 1 Hz"])
    if isinstance(current_profile, bool) or not isinstance(current_profile, int) or current_profile not in (1, 2, 3):
        raise IncompatibleFeatures(["current_profile debe ser 1, 2 o 3"])
    elapsed: list[float] = []
    throughput: list[float] = []
    for index, sample in enumerate(samples):
        if sample.get("unit") != "Mbps":
            raise IncompatibleFeatures([f"muestra {index}: unidad requerida Mbps"])
        if sample.get("source") != PREDICTIVE_COMPATIBLE_SOURCE:
            raise IncompatibleFeatures([f"muestra {index}: bitrate de OBS no es capacidad de red compatible"])
        raw_time = sample.get("elapsed_seconds")
        raw_value = sample.get("throughput_mbps")
        if isinstance(raw_time, bool) or not isinstance(raw_time, (int, float)) or not math.isfinite(float(raw_time)):
            raise IncompatibleFeatures([f"muestra {index}: elapsed_seconds inválido"])
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)) or not math.isfinite(float(raw_value)):
            raise IncompatibleFeatures([f"muestra {index}: throughput_mbps inválido"])
        if float(raw_value) < 0:
            raise IncompatibleFeatures([f"muestra {index}: throughput_mbps no puede ser negativo"])
        elapsed.append(float(raw_time))
        throughput.append(float(raw_value))
    normalized = [value - elapsed[0] for value in elapsed]
    expected = [float(index) for index in range(required_count)]
    if any(abs(actual - target) > 1e-6 for actual, target in zip(normalized, expected, strict=True)):
        raise IncompatibleFeatures([
            f"la ventana predictiva debe contener {required_count} muestras ordenadas a intervalos de 1 s"
        ])
    row = build_feature_row(
        throughput, normalized, current_profile, lookback_duration_seconds=float(contract["lookback_seconds"])
    )
    validate_generated_features(row, contract)
    return row
