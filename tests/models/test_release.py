import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.streamml.features.predictive_features import frame_in_contract_order, load_feature_contract
from src.streamml.services.release import sha256_file


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "models" / "registry"


def load_manifest() -> dict:
    return json.loads((RELEASE / "release_manifest.json").read_text(encoding="utf-8"))


def test_release_files_exist_and_hashes_match() -> None:
    manifest = load_manifest()
    assert manifest["official_release"] is True
    for relative, expected_hash in manifest["sha256_hashes"].items():
        path = ROOT / relative
        assert path.exists()
        assert sha256_file(path) == expected_hash


def test_reactive_release_predicts_probabilities() -> None:
    model = joblib.load(RELEASE / "reactive" / "model.joblib")
    contract = json.loads((RELEASE / "reactive" / "feature_contract.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(ROOT / "data" / "processed" / "reactive_dataset.csv")
    row = frame.loc[frame["split"] == "test"].iloc[[0]]
    x = row.loc[:, contract["features"]]
    pred = model.predict(x)
    proba = model.predict_proba(x)
    assert str(pred[0]) in {"low", "medium", "high"}
    assert proba.shape == (1, 3)
    assert np.isfinite(proba).all()


def test_predictive_release_predicts_with_threshold() -> None:
    model = joblib.load(RELEASE / "predictive" / "model.joblib")
    contract = load_feature_contract(RELEASE / "predictive" / "feature_contract.json")
    threshold = json.loads((RELEASE / "predictive" / "threshold.json").read_text(encoding="utf-8"))["threshold"]
    model_manifest = json.loads((RELEASE / "predictive" / "training_manifest.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(ROOT / "data" / "processed" / "predictive_dataset.csv")
    row = frame.loc[frame["session_id"].isin(model_manifest["splits"]["test"])].iloc[[0]]
    x = frame_in_contract_order(row, contract)
    proba = model.predict_proba(x)
    classes = list(model.classes_)
    positive = proba[0, classes.index(1)]
    pred = "downgrade_needed" if positive >= threshold else "maintain"
    assert pred in {"maintain", "downgrade_needed"}
    assert 0.0 <= positive <= 1.0


def test_release_models_are_ready() -> None:
    manifest = load_manifest()
    assert manifest["reactive_model_ready"] is True
    assert manifest["predictive_model_ready"] is True
