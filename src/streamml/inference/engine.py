"""Thread-safe inference over only the verified official artifacts."""

from __future__ import annotations

import hashlib
import json
from threading import Lock
from typing import Any

import pandas as pd

from src.streamml.features.predictive_window import build_predictive_features
from src.streamml.features.validation import validate_reactive_features

from .registry import OfficialModelRegistry


class InferenceEngine:
    def __init__(self, registry: OfficialModelRegistry) -> None:
        self.registry = registry
        self._lock = Lock()

    @staticmethod
    def fingerprint(payload: Any) -> str:
        serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    def predict_reactive(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        contract = self.registry.contracts["reactive"]
        values = validate_reactive_features(items, contract)
        frame = pd.DataFrame([[values[name] for name in contract["features"]]], columns=contract["features"])
        model = self.registry.models["reactive"]
        with self._lock:
            prediction = str(model.predict(frame)[0])
            probabilities = model.predict_proba(frame)[0]
        probability_by_label = {
            str(label): float(probability)
            for label, probability in zip(model.classes_, probabilities, strict=True)
        }
        confidence = probability_by_label[prediction]
        return {
            "prediction": prediction,
            "probabilities": probability_by_label,
            "explanation": (
                f"El modelo recomienda {prediction} con {confidence:.0%} de confianza. "
                f"Observó {values['upload_mbps']:.2f} Mbps de subida, "
                f"{values['download_mbps']:.2f} Mbps de descarga y "
                f"{values['latency_ms']:.1f} ms de latencia."
            ),
            "evidence": {
                "confidence": confidence,
                "upload_mbps": values["upload_mbps"],
                "download_mbps": values["download_mbps"],
                "latency_ms": values["latency_ms"],
                "interpretation": "observed_inputs_not_causal_attribution",
            },
        }

    def predict_predictive(self, samples: list[dict[str, Any]], current_profile: int) -> dict[str, Any]:
        contract = self.registry.contracts["predictive"]
        row = build_predictive_features(samples, current_profile, contract)
        frame = pd.DataFrame([[row[name] for name in contract["features"]]], columns=contract["features"])
        model = self.registry.models["predictive"]
        positive_code = self.registry.class_mappings["predictive"]["downgrade_needed"]
        classes = list(model.classes_)
        if positive_code not in classes:
            raise RuntimeError("The verified predictive positive class is unavailable.")
        with self._lock:
            probabilities = model.predict_proba(frame)[0]
        probability = float(probabilities[classes.index(positive_code)])
        decision = "downgrade_needed" if probability >= self.registry.threshold else "maintain"
        profile_name = {1: "low", 2: "medium", 3: "high"}[current_profile]
        below_key = {
            1: "proportion_below_low",
            2: "proportion_below_medium",
            3: "proportion_below_high",
        }[current_profile]
        below_required = float(row[below_key])
        relation = "alcanza o supera" if probability >= self.registry.threshold else "no alcanza"
        return {
            "decision": decision,
            "probability_downgrade_needed": probability,
            "probability_maintain": 1.0 - probability,
            "threshold": self.registry.threshold,
            "explanation": (
                f"El riesgo estimado es {probability:.0%} y {relation} el umbral de "
                f"{self.registry.threshold:.0%} para el perfil {profile_name}. "
                f"El percentil 10 fue {float(row['throughput_p10']):.2f} Mbps, "
                f"la capacidad requerida {float(row['required_capacity_mbps']):.2f} Mbps "
                f"y {below_required:.0%} de la ventana estuvo por debajo de esa capacidad."
            ),
            "evidence": {
                "current_profile": profile_name,
                "threshold": self.registry.threshold,
                "throughput_p10_mbps": float(row["throughput_p10"]),
                "throughput_slope_mbps_per_second": float(row["throughput_slope"]),
                "required_capacity_mbps": float(row["required_capacity_mbps"]),
                "proportion_below_required": below_required,
                "interpretation": "observed_window_summary_not_causal_attribution",
            },
        }
