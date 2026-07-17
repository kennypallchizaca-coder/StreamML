"""Leakage-safe StreamML predictive feature calculations."""

from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path

import numpy as np
import pandas as pd


PROFILE_CAPACITY = {1: 1.35, 2: 3.375, 3: 6.75}
FEATURE_COLUMNS = [
    "throughput_mean",
    "throughput_median",
    "throughput_min",
    "throughput_max",
    "throughput_std",
    "throughput_p10",
    "throughput_p25",
    "throughput_first",
    "throughput_last",
    "throughput_change",
    "throughput_slope",
    "throughput_coefficient_variation",
    "measurements_count",
    "lookback_duration_seconds",
    "proportion_below_low",
    "proportion_below_medium",
    "proportion_below_high",
    "current_profile",
    "required_capacity_mbps",
]
FORBIDDEN_FEATURES = {
    "future_throughput_mean",
    "future_throughput_p25",
    "future_rebuffer_event",
    "future_quality_decrease",
    "future_below_required_fraction",
    "target",
    "target_code",
}


def build_feature_row(
    throughput_mbps: Sequence[float],
    elapsed_seconds: Sequence[float],
    current_profile: int,
    lookback_duration_seconds: float = 120.0,
) -> dict[str, float | int]:
    """Calculate the inherited 19-feature contract from one historical window."""

    throughput = np.asarray(throughput_mbps, dtype=float)
    elapsed = np.asarray(elapsed_seconds, dtype=float)
    if throughput.ndim != 1 or elapsed.ndim != 1 or len(throughput) != len(elapsed):
        raise ValueError("throughput_mbps and elapsed_seconds must be one-dimensional and equally sized.")
    if len(throughput) < 2:
        raise ValueError("At least two historical measurements are required.")
    if not np.isfinite(throughput).all() or not np.isfinite(elapsed).all():
        raise ValueError("Feature inputs must contain only finite values.")
    if (throughput < 0).any():
        raise ValueError("throughput_mbps cannot contain negative values.")
    if (np.diff(elapsed) <= 0).any():
        raise ValueError("elapsed_seconds must be strictly increasing.")
    if current_profile not in PROFILE_CAPACITY:
        raise ValueError("current_profile must be one of 1, 2 or 3.")

    mean = float(np.mean(throughput))
    std = float(np.std(throughput, ddof=0))
    first = float(throughput[0])
    last = float(throughput[-1])
    row: dict[str, float | int] = {
        "throughput_mean": mean,
        "throughput_median": float(np.median(throughput)),
        "throughput_min": float(np.min(throughput)),
        "throughput_max": float(np.max(throughput)),
        "throughput_std": std,
        "throughput_p10": float(np.percentile(throughput, 10)),
        "throughput_p25": float(np.percentile(throughput, 25)),
        "throughput_first": first,
        "throughput_last": last,
        "throughput_change": last - first,
        "throughput_slope": float(np.polyfit(elapsed, throughput, 1)[0]),
        "throughput_coefficient_variation": std / mean if mean > 0 else 0.0,
        "measurements_count": int(len(throughput)),
        "lookback_duration_seconds": float(lookback_duration_seconds),
        "proportion_below_low": float(np.mean(throughput < PROFILE_CAPACITY[1])),
        "proportion_below_medium": float(np.mean(throughput < PROFILE_CAPACITY[2])),
        "proportion_below_high": float(np.mean(throughput < PROFILE_CAPACITY[3])),
        "current_profile": int(current_profile),
        "required_capacity_mbps": float(PROFILE_CAPACITY[current_profile]),
    }
    return {column: row[column] for column in FEATURE_COLUMNS}


def load_feature_contract(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        contract = json.load(handle)
    if contract["features"] != FEATURE_COLUMNS or contract["feature_count"] != len(FEATURE_COLUMNS):
        raise ValueError("The JSON feature contract does not match the inherited 19-feature order.")
    return contract


def validate_training_frame(frame: pd.DataFrame, contract: dict) -> None:
    features = contract["features"]
    if features != FEATURE_COLUMNS:
        raise ValueError("Unexpected feature order in contract.")
    missing = [column for column in features if column not in frame.columns]
    if missing:
        raise ValueError(f"Training frame is missing features: {missing}")
    leaked = FORBIDDEN_FEATURES.intersection(features)
    if leaked:
        raise ValueError(f"Forbidden future or target features in contract: {sorted(leaked)}")
    values = frame[features].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Training features contain non-finite values.")


def frame_in_contract_order(frame: pd.DataFrame, contract: dict) -> pd.DataFrame:
    validate_training_frame(frame, contract)
    return frame.loc[:, contract["features"]].copy()
