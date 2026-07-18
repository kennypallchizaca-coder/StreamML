"""Fail-closed loader for the hash-verified official StreamML release."""

from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import math
from pathlib import Path
from typing import Any

import joblib


MODEL_RUNTIME_PACKAGES = {"pandas", "numpy", "scikit-learn", "joblib"}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError(f"Official artifact is not a JSON object: {path.name}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class OfficialModelRegistry:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir.resolve()
        self.release_dir = self.root_dir / "models" / "registry"
        self.release = _read_json(self.release_dir / "release_manifest.json")
        self._validate_release_hashes()
        self._validate_runtime_versions()
        self.models: dict[str, Any] = {}
        self.contracts: dict[str, dict[str, Any]] = {}
        self.class_mappings: dict[str, dict[str, Any]] = {}
        self.metrics: dict[str, dict[str, Any]] = {}
        self.training_manifests: dict[str, dict[str, Any]] = {}
        self._load_role("reactive")
        self._load_role("predictive")
        self.threshold = self._load_threshold()

    @property
    def version(self) -> str:
        return str(self.release["release_version"])

    def _validate_release_hashes(self) -> None:
        if self.release.get("official_release") is not True:
            raise RuntimeError("The configured model release is not marked official.")
        hashes = self.release.get("sha256_hashes")
        if not isinstance(hashes, dict) or not hashes:
            raise RuntimeError("The official release does not contain artifact hashes.")
        for relative, expected in hashes.items():
            candidate = (self.root_dir / relative).resolve()
            if self.root_dir not in candidate.parents or not candidate.is_file():
                raise RuntimeError(f"Missing or invalid official artifact: {relative}")
            if _sha256(candidate) != expected:
                raise RuntimeError(f"Official artifact hash mismatch: {relative}")

    def _validate_runtime_versions(self) -> None:
        declared: dict[str, str] = {}
        for item in self.release.get("library_versions", []):
            if "==" in item:
                package, declared_version = item.split("==", 1)
                if package in MODEL_RUNTIME_PACKAGES:
                    declared[package] = declared_version
        for package in MODEL_RUNTIME_PACKAGES:
            if package not in declared:
                raise RuntimeError(f"Missing official runtime version for {package}.")
            try:
                installed = version(package)
            except PackageNotFoundError as exc:
                raise RuntimeError(f"Required model runtime package is missing: {package}") from exc
            if installed != declared[package]:
                raise RuntimeError(
                    f"Incompatible {package} runtime: expected {declared[package]}, found {installed}."
                )

    def _load_role(self, role: str) -> None:
        directory = self.release_dir / role
        contract = _read_json(directory / "feature_contract.json")
        mapping = _read_json(directory / "class_mapping.json")
        metrics = _read_json(directory / "metrics.json")
        training = _read_json(directory / "training_manifest.json")
        model = joblib.load(directory / "model.joblib")
        features = contract.get("features")
        if not isinstance(features, list) or contract.get("feature_count") != len(features):
            raise RuntimeError(f"Invalid {role} feature contract.")
        if list(map(str, getattr(model, "feature_names_in_", []))) != features:
            raise RuntimeError(f"{role} model feature order does not match its official contract.")
        if int(getattr(model, "n_features_in_", -1)) != len(features):
            raise RuntimeError(f"{role} model feature count does not match its official contract.")
        declared_model = self.release[f"{role}_model"]["selected_model"]
        estimator = getattr(model, "named_steps", {}).get("model", model)
        if type(estimator).__name__ != declared_model:
            raise RuntimeError(f"Unexpected official {role} model type.")
        classes = list(getattr(model, "classes_", []))
        expected_classes = list(mapping.keys()) if role == "reactive" else list(mapping.values())
        if set(map(str, classes)) != set(map(str, expected_classes)):
            raise RuntimeError(f"{role} model classes do not match class_mapping.json.")
        self.models[role] = model
        self.contracts[role] = contract
        self.class_mappings[role] = mapping
        self.metrics[role] = metrics
        self.training_manifests[role] = training

    def _load_threshold(self) -> float:
        artifact = _read_json(self.release_dir / "predictive" / "threshold.json")
        if "threshold" not in artifact:
            raise RuntimeError("The official predictive threshold is missing.")
        threshold = artifact["threshold"]
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
            raise RuntimeError("The official predictive threshold is invalid.")
        declared = self.release["predictive_model"].get("threshold")
        if threshold != declared:
            raise RuntimeError("Predictive threshold artifacts disagree.")
        return float(threshold)

    def public_models(self) -> list[dict[str, Any]]:
        result = []
        for role in ("reactive", "predictive"):
            release_model = self.release[f"{role}_model"]
            contract = self.contracts[role]
            metrics = self.metrics[role]
            training = self.training_manifests[role]
            public_feature_metadata = None
            if contract.get("feature_metadata"):
                public_fields = {"definition", "unit", "training_source", "formula", "availability"}
                public_feature_metadata = {
                    name: {
                        key: value
                        for key, value in metadata.items()
                        if key in public_fields
                    }
                    for name, metadata in contract["feature_metadata"].items()
                }
            item: dict[str, Any] = {
                "role": role,
                "version": self.version,
                "algorithm": release_model["selected_model"],
                "official_release": True,
                "features": contract["features"],
                "feature_metadata": public_feature_metadata,
                "formulas": contract.get("formulas"),
                "classes": list(self.class_mappings[role].keys()),
                "status": "official",
                "validation": release_model.get("validation"),
                "test": release_model.get("test"),
                "baseline": release_model.get("baseline"),
                "dataset": metrics.get("dataset"),
                "trained_at": training.get("created_at_utc"),
                "split_method": training.get("split_method"),
                "split_counts": (
                    training.get("split_window_counts")
                    or training.get("split_rows")
                ),
                "generalization_gap": metrics.get("generalization_gap"),
                "improvement_over_baseline_macro_f1": (
                    metrics.get("improvement_over_dummy_test_macro_f1")
                    if role == "predictive"
                    else metrics.get("improvement_over_baseline_test_macro_f1")
                ),
                "model_comparison": {
                    name: {
                        "best_parameters": values.get("best_parameters"),
                        "train_groupkfold_macro_f1": values.get("train_groupkfold_macro_f1"),
                        "validation": {
                            key: (values.get("validation") or {}).get(key)
                            for key in ("macro_f1", "balanced_accuracy", "accuracy")
                        },
                    }
                    for name, values in (metrics.get("model_comparison") or {}).items()
                },
                "feature_importance": (metrics.get("feature_importance") or [])[:8],
                "limitations": self._public_limitations(role),
                "metrics": {
                    "validation": release_model.get("validation"),
                    "test": release_model.get("test"),
                    "baseline": release_model.get("baseline"),
                },
            }
            if role == "predictive":
                item["threshold"] = self.threshold
                item["lookback_seconds"] = contract["lookback_seconds"]
                item["future_horizon_seconds"] = contract["future_horizon_seconds"]
            result.append(item)
        return result

    def _public_limitations(self, role: str) -> list[str]:
        metrics = self.metrics[role]
        if role == "reactive":
            return [
                "El target es una pseudoetiqueta derivada de reglas de capacidad y latencia.",
                "Las métricas validan la reproducción de esa regla; la mejora de QoE debe comprobarse con transmisiones físicas.",
            ]
        dataset = metrics.get("dataset") or {}
        sessions = dataset.get("sessions", "un número limitado de")
        return [
            f"El dataset público predictivo contiene {sessions} sesiones y requiere más diversidad móvil para generalizar.",
            "Las ventanas temporales se solapan y no deben interpretarse como observaciones independientes.",
            "La capacidad de entrenamiento es un proxy del dataset fuente; la validación final debe usar la ruta real del teléfono.",
        ]
