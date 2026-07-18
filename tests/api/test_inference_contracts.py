import json

import pandas as pd
from fastapi.testclient import TestClient

from src.streamml.features.validation import validate_generated_features
from src.streamml.inference.registry import OfficialModelRegistry

from conftest import ROOT, create_session, login


def test_customer_model_catalog_contains_no_legacy_surface_metadata(client: TestClient):
    login(client)
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    legacy_surface_token = "off" + "line"
    assert legacy_surface_token not in json.dumps(response.json()).lower()


def test_official_registry_runs_both_unmodified_models():
    registry = OfficialModelRegistry(ROOT)
    reactive = pd.read_csv(ROOT / "data" / "processed" / "reactive_dataset.csv").iloc[[0]]
    reactive_contract = registry.contracts["reactive"]
    assert str(registry.models["reactive"].predict(reactive[reactive_contract["features"]])[0]) in {
        "low", "medium", "high"
    }

    predictive = pd.read_csv(ROOT / "data" / "processed" / "predictive_dataset.csv").iloc[[0]]
    predictive_contract = registry.contracts["predictive"]
    assert int(registry.models["predictive"].predict(predictive[predictive_contract["features"]])[0]) in {0, 1}
    assert registry.threshold == 0.5


def test_official_negative_slope_is_not_rejected():
    registry = OfficialModelRegistry(ROOT)
    contract = registry.contracts["predictive"]
    frame = pd.read_csv(ROOT / "data" / "processed" / "predictive_dataset.csv")
    row = frame.loc[frame["throughput_slope"] < 0, contract["features"]].iloc[0].to_dict()
    validate_generated_features(row, contract)


def test_reactive_prediction_executes_only_with_exact_contract(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    row = pd.read_csv(ROOT / "data" / "processed" / "reactive_dataset.csv").iloc[0]
    features = [
        {"name": "upload_mbps", "value": float(row.upload_mbps), "unit": "Mbps", "source": "rtr_netztest_compatible_measurement"},
        {"name": "download_mbps", "value": float(row.download_mbps), "unit": "Mbps", "source": "rtr_netztest_compatible_measurement"},
        {"name": "latency_ms", "value": float(row.latency_ms), "unit": "ms", "source": "rtr_netztest_compatible_measurement"},
    ]
    response = client.post("/api/v1/predict/reactive", json={"session_id": session_id, "features": features})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "executed"

    features[0]["source"] = "obs_websocket_5"
    blocked = client.post("/api/v1/predict/reactive", json={"session_id": session_id, "features": features})
    assert blocked.status_code == 422
    assert blocked.json()["message"] == "Datos insuficientes para una predicción válida"


def test_predictive_rejects_obs_bitrate_without_imputation(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    samples = [
        {"elapsed_seconds": index, "throughput_mbps": 4.0, "unit": "Mbps", "source": "obs_websocket_5"}
        for index in range(600)
    ]
    response = client.post(
        "/api/v1/predict/predictive",
        json={"session_id": session_id, "samples": samples, "current_profile": 2},
    )
    assert response.status_code == 422
    assert response.json()["message"] == "Datos insuficientes para una predicción válida"
