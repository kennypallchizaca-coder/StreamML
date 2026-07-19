import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "processed" / "predictive_dataset.csv"


def load_dataset() -> pd.DataFrame:
    assert DATASET.exists(), "Run scripts/prepare_datasets.py first."
    return pd.read_csv(DATASET)


def test_each_window_belongs_to_exactly_one_session() -> None:
    frame = load_dataset()
    assert frame["window_id"].is_unique
    assert all(window.startswith(f"{session}_w") for window, session in zip(frame["window_id"], frame["session_id"]))


def test_window_and_future_timing_contract() -> None:
    frame = load_dataset()
    config = json.loads(
        (ROOT / "src" / "streamml" / "config" / "dataset_config.json").read_text()
    )
    lookback = float(config["windowing"]["lookback_seconds"])
    horizon = float(config["windowing"]["future_horizon_seconds"])
    np.testing.assert_allclose(frame["window_end_seconds"] - frame["window_start_seconds"], lookback)
    assert (frame["future_window_start_seconds"] >= frame["window_end_seconds"]).all()
    np.testing.assert_allclose(
        frame["future_window_end_seconds"] - frame["future_window_start_seconds"], horizon
    )
    assert (frame["future_measurements_count"] == horizon).all()


def test_profiles_capacities_proportions_and_targets() -> None:
    frame = load_dataset()
    assert set(frame["current_profile"].unique()).issubset({1, 2, 3})
    expected_capacity = frame["current_profile"].map({1: 1.35, 2: 3.375, 3: 6.75})
    np.testing.assert_allclose(frame["required_capacity_mbps"], expected_capacity)
    proportions = frame[["proportion_below_low", "proportion_below_medium", "proportion_below_high"]]
    assert ((proportions >= 0) & (proportions <= 1)).all().all()
    assert set(frame["target"].unique()).issubset({"maintain", "downgrade_needed"})
    expected_codes = frame["target"].map({"maintain": 0, "downgrade_needed": 1})
    assert np.array_equal(frame["target_code"].to_numpy(), expected_codes.to_numpy())


def test_target_is_reconstructed_only_from_future_conditions() -> None:
    frame = load_dataset()
    reconstructed = (
        frame["target_trigger_rebuffer"].astype(bool)
        | frame["target_trigger_p25"].astype(bool)
        | frame["target_trigger_fraction"].astype(bool)
        | frame["target_trigger_quality_decrease"].astype(bool)
    ).astype(int)
    assert np.array_equal(frame["target_code"].to_numpy(), reconstructed.to_numpy())


def test_dataset_contains_required_source_and_target_metadata() -> None:
    frame = load_dataset()
    assert {"source_dataset", "source_version", "session_id", "window_id", "target", "target_code"}.issubset(
        frame.columns
    )
    assert frame["source_dataset"].notna().all()
    assert frame["source_version"].notna().all()
