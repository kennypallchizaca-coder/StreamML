import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.predictive_features import (
    FEATURE_COLUMNS,
    FORBIDDEN_FEATURES,
    build_feature_row,
    load_feature_contract,
    validate_training_frame,
)


ROOT = Path(__file__).resolve().parents[1]


def test_slope_uses_real_elapsed_seconds_not_row_number() -> None:
    row = build_feature_row([0.0, 1.0, 10.0], [0.0, 1.0, 10.0], current_profile=1)
    assert row["throughput_slope"] == pytest.approx(1.0)
    row_index_slope = np.polyfit(np.arange(3), np.array([0.0, 1.0, 10.0]), 1)[0]
    assert row["throughput_slope"] != pytest.approx(row_index_slope)


def test_feature_order_matches_official_contract() -> None:
    contract = load_feature_contract(ROOT / "config" / "predictive_feature_contract.json")
    assert contract["contract_version"] == "2.0.0-official"
    assert contract["features"] == FEATURE_COLUMNS
    assert len(contract["features"]) == 19
    assert contract["lookback_seconds"] == 120
    assert contract["future_horizon_seconds"] == 30


def test_future_and_target_columns_are_not_model_inputs() -> None:
    contract = load_feature_contract(ROOT / "config" / "predictive_feature_contract.json")
    assert not FORBIDDEN_FEATURES.intersection(contract["features"])
    frame = pd.read_csv(ROOT / "data" / "processed" / "predictive_dataset.csv")
    validate_training_frame(frame, contract)


def test_feature_calculation_has_valid_profile_capacity_and_proportions() -> None:
    row = build_feature_row([1.0, 2.0, 4.0, 8.0], [0.0, 2.0, 5.0, 9.0], current_profile=2)
    assert row["current_profile"] == 2
    assert row["required_capacity_mbps"] == pytest.approx(3.375)
    for column in ("proportion_below_low", "proportion_below_medium", "proportion_below_high"):
        assert 0.0 <= row[column] <= 1.0
