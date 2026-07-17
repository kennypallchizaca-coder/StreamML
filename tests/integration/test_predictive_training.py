import json
from pathlib import Path
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd

from src.streamml.features.predictive_features import frame_in_contract_order, load_feature_contract
from src.streamml.training.predictive import positive_probability


ROOT = Path(__file__).resolve().parents[2]
PREDICTIVE_RELEASE = ROOT / "models" / "registry" / "predictive"


def load_manifest() -> dict:
    return json.loads((PREDICTIVE_RELEASE / "training_manifest.json").read_text(encoding="utf-8"))


def test_train_validation_test_sessions_are_disjoint() -> None:
    splits = load_manifest()["splits"]
    train, validation, test = map(set, (splits["train"], splits["validation"], splits["test"]))
    assert train.isdisjoint(validation)
    assert train.isdisjoint(test)
    assert validation.isdisjoint(test)


def test_model_option_loads_and_predict_proba_is_finite() -> None:
    model = joblib.load(PREDICTIVE_RELEASE / "model.joblib")
    contract = load_feature_contract(PREDICTIVE_RELEASE / "feature_contract.json")
    manifest = load_manifest()
    frame = pd.read_csv(ROOT / "data" / "processed" / "predictive_dataset.csv")
    test_row = frame.loc[frame["session_id"].isin(manifest["splits"]["test"])].iloc[[0]]
    X = frame_in_contract_order(test_row, contract)
    probability = positive_probability(model, X)
    assert probability.shape == (1,)
    assert np.isfinite(probability).all()
    assert ((probability >= 0) & (probability <= 1)).all()


def test_required_release_statuses_are_official() -> None:
    manifest = load_manifest()
    assert manifest["official_release"] is True
    assert manifest["predictive_model_ready"] is True
    assert manifest["validated_with_public_dataset"] is True


def test_demo_completes_without_external_services() -> None:
    demo_path = ROOT / "scripts" / "demo_models.py"
    source = demo_path.read_text(encoding="utf-8").lower()
    assert "streamml demo completed" in source
    completed = subprocess.run(
        [sys.executable, str(demo_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "STREAMML DEMO COMPLETED" in completed.stdout
