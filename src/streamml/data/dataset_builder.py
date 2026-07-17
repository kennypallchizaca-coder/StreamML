"""Build the public, session-safe StreamML predictive dataset."""

from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.streamml.features.predictive_features import build_feature_row


MINIMUM_OUTPUT_COLUMNS = [
    "source_dataset",
    "source_version",
    "session_id",
    "window_id",
    "window_start_seconds",
    "window_end_seconds",
    "sampling_interval_seconds",
    "measurements_count",
    "current_profile",
    "required_capacity_mbps",
    "throughput_mean",
    "throughput_median",
    "throughput_min",
    "throughput_max",
    "throughput_std",
    "throughput_p25",
    "throughput_p75",
    "throughput_coefficient_variation",
    "throughput_slope",
    "throughput_change",
    "proportion_below_low",
    "proportion_below_medium",
    "proportion_below_high",
    "future_throughput_mean",
    "future_throughput_p25",
    "future_rebuffer_event",
    "target",
    "target_code",
]


def _to_epoch_seconds(values: pd.Series) -> np.ndarray:
    parsed = pd.to_datetime(values, utc=True, errors="coerce")
    if parsed.isna().any():
        raise ValueError("Application timestamp contains invalid values.")
    nanoseconds = parsed.to_numpy(dtype="datetime64[ns]").astype("int64")
    return nanoseconds.astype(float) / 1_000_000_000.0


def _load_session(session_dir: Path, itag_mapping: dict[int, int]) -> tuple[pd.DataFrame, pd.DataFrame, Counter]:
    application = pd.read_csv(session_dir / "application_data.csv")
    bandwidth = pd.read_csv(session_dir / "bw_settings.csv")
    required_application = {"timestamp", "fmt", "stalling"}
    if not required_application.issubset(application.columns):
        raise ValueError(f"Missing application columns in {session_dir.name}.")
    if not {"timestamp", "bandwidth"}.issubset(bandwidth.columns):
        raise ValueError(f"Missing bandwidth columns in {session_dir.name}.")

    application = application.copy()
    application["epoch_seconds"] = _to_epoch_seconds(application["timestamp"])
    application["fmt"] = pd.to_numeric(application["fmt"], errors="coerce").astype("Int64")
    application["stalling"] = pd.to_numeric(application["stalling"], errors="coerce").fillna(0).astype(int)
    application["profile"] = application["fmt"].map(itag_mapping).astype("Int64")
    application = application.sort_values("epoch_seconds").drop_duplicates("epoch_seconds", keep="last")
    unknown_formats = Counter(
        str(int(code)) for code in application.loc[application["profile"].isna(), "fmt"].dropna().tolist()
    )

    bandwidth = bandwidth.copy()
    bandwidth["timestamp"] = pd.to_numeric(bandwidth["timestamp"], errors="coerce")
    bandwidth["bandwidth"] = pd.to_numeric(bandwidth["bandwidth"], errors="coerce")
    bandwidth = bandwidth.dropna(subset=["timestamp", "bandwidth"])
    bandwidth = bandwidth.loc[bandwidth["bandwidth"] > 0].sort_values("timestamp")
    bandwidth = bandwidth.drop_duplicates("timestamp", keep="last")
    if bandwidth.empty or application.empty:
        raise ValueError(f"Empty synchronized source data in {session_dir.name}.")
    bandwidth["throughput_mbps"] = bandwidth["bandwidth"] / 1000.0
    return application, bandwidth, unknown_formats


def _sample_capacity(bandwidth: pd.DataFrame, sample_times: np.ndarray) -> np.ndarray:
    timestamps = bandwidth["timestamp"].to_numpy(dtype=float)
    capacity = bandwidth["throughput_mbps"].to_numpy(dtype=float)
    indices = np.searchsorted(timestamps, sample_times, side="right") - 1
    if (indices < 0).any():
        raise ValueError("A requested sample predates the first bandwidth setting.")
    return capacity[indices]


def build_session_windows(
    session_dir: Path,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], Counter, Counter]:
    window_config = config["windowing"]
    lookback = int(window_config["lookback_seconds"])
    future_horizon = int(window_config["future_horizon_seconds"])
    step = int(window_config["step_seconds"])
    sampling = float(window_config["sampling_interval_seconds"])
    itag_mapping = {int(key): int(value) for key, value in config["profiles"]["youtube_itag_to_profile"].items()}
    application, bandwidth, unknown_formats = _load_session(session_dir, itag_mapping)
    discards: Counter = Counter()

    session_start = math.ceil(max(application["epoch_seconds"].min(), bandwidth["timestamp"].min()))
    session_end = math.floor(application["epoch_seconds"].max())
    if session_end - session_start < lookback + future_horizon:
        discards["session_too_short"] += 1
        return [], discards, unknown_formats

    rows: list[dict[str, Any]] = []
    max_offset = session_end - session_start - lookback - future_horizon
    for offset in range(0, max_offset + 1, step):
        history_start = float(session_start + offset)
        history_end = history_start + lookback
        future_end = history_end + future_horizon
        history_times = np.arange(history_start, history_end, sampling)
        future_times = np.arange(history_end, future_end, sampling)
        if len(history_times) != int(window_config["minimum_measurements"]):
            discards["insufficient_historical_measurements"] += 1
            continue
        if len(future_times) == 0 or future_times.min() < history_end:
            discards["invalid_future_horizon"] += 1
            continue

        historical_throughput = _sample_capacity(bandwidth, history_times)
        future_throughput = _sample_capacity(bandwidth, future_times)
        historical_app = application.loc[
            (application["epoch_seconds"] >= history_start)
            & (application["epoch_seconds"] < history_end)
        ]
        future_app = application.loc[
            (application["epoch_seconds"] >= history_end)
            & (application["epoch_seconds"] < future_end)
        ]
        if historical_app.empty:
            discards["missing_historical_application"] += 1
            continue
        current_profile_value = historical_app.iloc[-1]["profile"]
        if pd.isna(current_profile_value):
            discards["incompatible_current_quality"] += 1
            continue
        if future_app.empty:
            discards["missing_future_application"] += 1
            continue

        current_profile = int(current_profile_value)
        features = build_feature_row(
            historical_throughput,
            history_times - history_start,
            current_profile,
            lookback_duration_seconds=lookback,
        )
        required_capacity = float(features["required_capacity_mbps"])
        future_rebuffer = bool((future_app["stalling"] == 1).any())
        known_future_profiles = future_app["profile"].dropna().astype(int)
        future_quality_decrease = bool((known_future_profiles < current_profile).any())
        future_mean = float(np.mean(future_throughput))
        future_p25 = float(np.percentile(future_throughput, 25))
        future_below_fraction = float(np.mean(future_throughput < required_capacity))
        conditions = {
            "rebuffer": future_rebuffer,
            "p25_below_required": future_p25 < required_capacity,
            "more_than_30pct_below_required": future_below_fraction
            > float(config["target"]["future_below_capacity_fraction"]),
            "quality_decrease": future_quality_decrease,
        }
        target_code = int(any(conditions.values()))
        target = "downgrade_needed" if target_code else "maintain"
        row: dict[str, Any] = {
            "source_dataset": config["source"]["source_dataset"],
            "source_version": config["source"]["source_version"],
            "session_id": session_dir.name,
            "window_id": f"{session_dir.name}_w{offset:06d}",
            "window_start_seconds": float(offset),
            "window_end_seconds": float(offset + lookback),
            "sampling_interval_seconds": sampling,
            **features,
            "throughput_p75": float(np.percentile(historical_throughput, 75)),
            "future_window_start_seconds": float(offset + lookback),
            "future_window_end_seconds": float(offset + lookback + future_horizon),
            "future_measurements_count": int(len(future_throughput)),
            "future_throughput_mean": future_mean,
            "future_throughput_p25": future_p25,
            "future_rebuffer_event": future_rebuffer,
            "future_below_required_fraction": future_below_fraction,
            "future_quality_decrease": future_quality_decrease,
            "target": target,
            "target_code": target_code,
            "quality_format_at_window_end": int(historical_app.iloc[-1]["fmt"]),
            "target_trigger_rebuffer": conditions["rebuffer"],
            "target_trigger_p25": conditions["p25_below_required"],
            "target_trigger_fraction": conditions["more_than_30pct_below_required"],
            "target_trigger_quality_decrease": conditions["quality_decrease"],
            "throughput_source": "bw_settings capacity proxy (kbit/s converted to Mbps)",
        }
        rows.append(row)
    return rows, discards, unknown_formats


def build_dataset(root: Path, config: dict[str, Any], source_manifest: dict[str, Any]) -> tuple[pd.DataFrame, dict]:
    raw_root = root / config["paths"]["raw_root"] / "sessions"
    selected = source_manifest["selection"]["selected_sessions"]
    all_rows: list[dict[str, Any]] = []
    discards: Counter = Counter()
    unknown_formats: Counter = Counter()
    used_sessions: list[str] = []
    for session_id in selected:
        rows, session_discards, session_unknown = build_session_windows(raw_root / session_id, config)
        all_rows.extend(rows)
        discards.update(session_discards)
        unknown_formats.update(session_unknown)
        if rows:
            used_sessions.append(session_id)
    if not all_rows:
        raise RuntimeError("No compatible predictive windows were generated.")

    frame = pd.DataFrame(all_rows).sort_values(["session_id", "window_start_seconds"]).reset_index(drop=True)
    missing = [column for column in MINIMUM_OUTPUT_COLUMNS if column not in frame.columns]
    if missing:
        raise RuntimeError(f"Output dataset is missing required columns: {missing}")
    statistics = {
        "source_sessions_selected": len(selected),
        "sessions_used": int(frame["session_id"].nunique()),
        "sessions_without_windows": sorted(set(selected) - set(used_sessions)),
        "windows_generated": len(frame),
        "class_distribution": {str(key): int(value) for key, value in frame["target"].value_counts().items()},
        "profile_distribution": {
            str(int(key)): int(value) for key, value in frame["current_profile"].value_counts().sort_index().items()
        },
        "discard_reasons": dict(sorted(discards.items())),
        "unknown_format_rows": dict(sorted(unknown_formats.items())),
        "windowing": config["windowing"],
        "target_definition": (
            f"downgrade_needed when the next {config['windowing']['future_horizon_seconds']} s contain a real stalling flag, future throughput p25 below "
            "the current profile capacity, more than 30% of future capacity samples below it, or a mapped "
            "YouTube quality decrease; otherwise maintain"
        ),
        "pseudo_label": True,
    }
    return frame, statistics


def build_schema(frame: pd.DataFrame) -> dict:
    descriptions = {
        "throughput_source": "Bandwidth setting used as a connection-capacity proxy.",
        "future_rebuffer_event": "Observed stalling field from application_data.csv in the future horizon.",
        "target": "Pseudo-label derived only from the strictly future horizon.",
    }
    return {
        "schema_version": "3.0.0",
        "row_semantics": "One 600-second historical window from exactly one session plus a subsequent 600-second label horizon.",
        "columns": [
            {
                "name": column,
                "dtype": str(frame[column].dtype),
                "description": descriptions.get(column, "See feature contract or dataset card."),
            }
            for column in frame.columns
        ],
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
