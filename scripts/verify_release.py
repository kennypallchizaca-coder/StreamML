"""Verify the complete official StreamML release."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.streamml.features.predictive_features import frame_in_contract_order, load_feature_contract
from src.streamml.services.release import sha256_file


def main() -> None:
    expected_notebooks = {
        "01_data_preparation.ipynb",
        "02_model_training.ipynb",
        "03_model_inference.ipynb",
        "04_entrenamiento_y_creacion_del_agente.ipynb",
    }
    assert {path.name for path in (ROOT / "notebooks").glob("*.ipynb")} == expected_notebooks
    assert {path.name for path in (ROOT / "scripts").glob("*.py")} == {
        "fetch_predictive_source.py",
        "prepare_datasets.py",
        "train_models.py",
        "evaluate_models.py",
        "demo_models.py",
        "verify_release.py",
        "check_no_secrets.py",
        "audit_ml_data.py",
        "evaluate_control_replay.py",
    }
    assert {path.name for path in (ROOT / "data" / "processed").glob("*") if path.is_file()} == {
        "reactive_dataset.csv",
        "predictive_dataset.csv",
    }
    release = ROOT / "models" / "registry"
    manifest = json.loads((release / "release_manifest.json").read_text(encoding="utf-8"))
    assert manifest["official_release"] is True
    for relative, expected in manifest["sha256_hashes"].items():
        assert sha256_file(ROOT / relative) == expected, f"Hash mismatch: {relative}"

    reactive = joblib.load(release / "reactive" / "model.joblib")
    reactive_contract = json.loads(
        (ROOT / "src" / "streamml" / "config" / "reactive_feature_contract.json").read_text(encoding="utf-8")
    )
    reactive_data = pd.read_csv(ROOT / "data" / "processed" / "reactive_dataset.csv")
    reactive_x = reactive_data.iloc[[0]].loc[:, reactive_contract["features"]]
    assert np.isfinite(reactive.predict_proba(reactive_x)).all()

    predictive = joblib.load(release / "predictive" / "model.joblib")
    predictive_contract = load_feature_contract(
        ROOT / "src" / "streamml" / "config" / "predictive_feature_contract.json"
    )
    predictive_data = pd.read_csv(ROOT / "data" / "processed" / "predictive_dataset.csv")
    predictive_x = frame_in_contract_order(predictive_data.iloc[[0]], predictive_contract)
    assert np.isfinite(predictive.predict_proba(predictive_x)).all()
    assert (
        manifest["predictive_model"]["test"]["macro_f1"] >= manifest["predictive_model"]["baseline"]["test"]["macro_f1"]
    )
    print("STREAMML RELEASE VERIFIED")


if __name__ == "__main__":
    main()
