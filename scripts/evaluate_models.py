"""Re-evaluate persisted models and refresh the official release manifest."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.predictive_training import evaluate_saved_release
from src.release_utils import file_hashes, read_json, requirements_snapshot, write_json


def artifact_files() -> list[Path]:
    names = ["model.joblib", "feature_contract.json", "metrics.json", "class_mapping.json",
             "training_manifest.json", "source_manifest.json", "requirements_snapshot.txt"]
    files = [ROOT / "models" / "release" / role / name for role in ("reactive", "predictive") for name in names]
    return files + [ROOT / "models" / "release" / "predictive" / "threshold.json"]


def main() -> None:
    config = read_json(ROOT / "config" / "dataset_config.json")
    predictive = evaluate_saved_release(ROOT, config)
    reactive = read_json(ROOT / "models" / "release" / "reactive" / "metrics.json")
    reactive_training = read_json(ROOT / "models" / "release" / "reactive" / "training_manifest.json")
    predictive_training = read_json(ROOT / "models" / "release" / "predictive" / "training_manifest.json")
    threshold = read_json(ROOT / "models" / "release" / "predictive" / "threshold.json")["threshold"]
    manifest = {
        "release_version": "2.0.0",
        "official_release": True,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "offline_release": True,
        "reactive_model_ready": True,
        "predictive_model_ready": True,
        "offline_demo_ready": True,
        "reactive_model": {
            "path": "models/release/reactive/model.joblib", "selected_model": reactive["selected_model"],
            "features": reactive_training["features"], "classes": reactive_training["classes"],
            "validation": reactive["validation"], "test": reactive["test"], "baseline": reactive["baseline"],
            "dataset": reactive_training["dataset_path"], "dataset_sha256": reactive_training["dataset_sha256"],
        },
        "predictive_model": {
            "path": "models/release/predictive/model.joblib", "selected_model": predictive["selected_model"],
            "features": predictive_training["features"], "classes": ["maintain", "downgrade_needed"],
            "threshold": threshold, "validation": predictive["validation"], "test": predictive["test"],
            "baseline": predictive["baseline"], "dataset": predictive_training["dataset_path"],
            "dataset_sha256": predictive_training["dataset_sha256"],
        },
        "random_state": config["random_state"],
        "library_versions": requirements_snapshot().strip().splitlines(),
    }
    manifest["sha256_hashes"] = file_hashes(artifact_files(), ROOT)
    write_json(ROOT / "models" / "release" / "release_manifest.json", manifest)
    print(json.dumps({
        "reactive_test_macro_f1": reactive["test"]["macro_f1"],
        "predictive_test_macro_f1": predictive["test"]["macro_f1"],
        "predictive_threshold": threshold,
    }, indent=2))


if __name__ == "__main__":
    main()
