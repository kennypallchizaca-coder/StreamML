"""Run one reproducible inference with each official model."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.streamml.features.predictive_features import frame_in_contract_order, load_feature_contract


def main() -> None:
    release = ROOT / "models" / "registry"
    reactive_model = joblib.load(release / "reactive" / "model.joblib")
    reactive_contract = json.loads(
        (ROOT / "src" / "streamml" / "config" / "reactive_feature_contract.json").read_text(
            encoding="utf-8"
        )
    )
    reactive_data = pd.read_csv(ROOT / "data" / "processed" / "reactive_dataset.csv")
    reactive_row = reactive_data.loc[reactive_data["split"] == "test"].iloc[[0]]
    reactive_x = reactive_row.loc[:, reactive_contract["features"]]

    predictive_model = joblib.load(release / "predictive" / "model.joblib")
    predictive_contract = load_feature_contract(
        ROOT / "src" / "streamml" / "config" / "predictive_feature_contract.json"
    )
    predictive_manifest = json.loads((release / "predictive" / "training_manifest.json").read_text(encoding="utf-8"))
    predictive_data = pd.read_csv(ROOT / "data" / "processed" / "predictive_dataset.csv")
    predictive_row = predictive_data.loc[predictive_data["session_id"].isin(predictive_manifest["splits"]["test"])].iloc[[0]]
    predictive_x = frame_in_contract_order(predictive_row, predictive_contract)
    probability = float(predictive_model.predict_proba(predictive_x)[0, list(predictive_model.classes_).index(1)])
    threshold = json.loads((release / "predictive" / "threshold.json").read_text(encoding="utf-8"))["threshold"]

    print(json.dumps({
        "reactive": {"prediction": str(reactive_model.predict(reactive_x)[0]), "actual": reactive_row["target"].iloc[0]},
        "predictive": {"probability_downgrade_needed": probability, "threshold": threshold,
                       "prediction": "downgrade_needed" if probability >= threshold else "maintain",
                       "actual": predictive_row["target"].iloc[0]},
    }, indent=2))
    print("STREAMML DEMO COMPLETED")


if __name__ == "__main__":
    main()
