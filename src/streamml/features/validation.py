"""Validación fail-closed de características: sin coerción, imputación o reordenamiento."""

from __future__ import annotations

import math
from typing import Any

from src.streamml.domain.contracts import INSUFFICIENT_DATA, REACTIVE_COMPATIBLE_SOURCES


class IncompatibleFeatures(ValueError):
    def __init__(self, details: list[str]) -> None:
        super().__init__(INSUFFICIENT_DATA)
        self.details = details


def _strict_number(value: Any, name: str, *, nonnegative: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IncompatibleFeatures([f"{name}: tipo numérico requerido"])
    numeric = float(value)
    if not math.isfinite(numeric):
        raise IncompatibleFeatures([f"{name}: valor finito requerido"])
    if nonnegative and numeric < 0:
        raise IncompatibleFeatures([f"{name}: no puede ser negativo"])
    return numeric


def validate_reactive_features(items: list[dict[str, Any]], contract: dict[str, Any]) -> dict[str, float]:
    expected = contract["features"]
    received = [item.get("name") for item in items]
    if received != expected:
        missing = [name for name in expected if name not in received]
        extra = [name for name in received if name not in expected]
        details = ["orden o nombres incompatibles"]
        if missing:
            details.append("faltantes: " + ", ".join(missing))
        if extra:
            details.append("no permitidas: " + ", ".join(map(str, extra)))
        raise IncompatibleFeatures(details)
    values: dict[str, float] = {}
    for item, name in zip(items, expected, strict=True):
        metadata = contract["feature_metadata"][name]
        if item.get("unit") != metadata["unit"]:
            raise IncompatibleFeatures([f"{name}: unidad requerida {metadata['unit']}"])
        if item.get("source") not in REACTIVE_COMPATIBLE_SOURCES:
            raise IncompatibleFeatures([f"{name}: fuente no compatible"])
        values[name] = _strict_number(item.get("value"), name)
    return values


def validate_generated_features(values: dict[str, Any], contract: dict[str, Any]) -> None:
    if list(values.keys()) != contract["features"]:
        raise IncompatibleFeatures(["las features derivadas no respetan el contrato oficial"])
    signed_features = {"throughput_change", "throughput_slope"}
    for name, value in values.items():
        _strict_number(value, name, nonnegative=name not in signed_features)
