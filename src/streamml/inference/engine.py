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
        return {
            "prediction": prediction,
            "probabilities": {
                str(label): float(probability)
                for label, probability in zip(model.classes_, probabilities, strict=True)
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
        return {
            "decision": decision,
            "probability_downgrade_needed": probability,
            "probability_maintain": 1.0 - probability,
            "threshold": self.registry.threshold,
        }
