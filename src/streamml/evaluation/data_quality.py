"""Evidence-oriented dataset audits that never modify training data."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _class_distribution(values: pd.Series) -> dict[str, dict[str, float | int]]:
    counts = values.astype(str).value_counts(dropna=False)
    total = max(1, int(counts.sum()))
    return {
        str(label): {"count": int(count), "fraction": float(count / total)}
        for label, count in counts.items()
    }


def _feature_fingerprints(frame: pd.DataFrame, feature_columns: list[str]) -> pd.Series:
    if not feature_columns:
        raise ValueError("At least one feature column is required for the audit.")
    missing = sorted(set(feature_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"Dataset is missing audited features: {missing}")
    return pd.util.hash_pandas_object(frame.loc[:, feature_columns], index=False)


def _missing_and_non_finite(
    frame: pd.DataFrame, feature_columns: list[str]
) -> tuple[dict[str, int], dict[str, int]]:
    missing: dict[str, int] = {}
    non_finite: dict[str, int] = {}
    for column in feature_columns:
        series = frame[column]
        missing[column] = int(series.isna().sum())
        if pd.api.types.is_numeric_dtype(series):
            numeric = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
            non_finite[column] = int(np.sum(~np.isfinite(numeric) & ~pd.isna(numeric)))
        else:
            non_finite[column] = 0
    return missing, non_finite


def _constant_features(frame: pd.DataFrame, feature_columns: list[str]) -> list[str]:
    return sorted(
        column for column in feature_columns if frame[column].nunique(dropna=False) <= 1
    )


def _split_for_sessions(
    frame: pd.DataFrame, splits: dict[str, list[str]]
) -> pd.Series:
    session_to_split: dict[str, str] = {}
    for split_name, sessions in splits.items():
        for session in sessions:
            if str(session) in session_to_split:
                raise ValueError("A session appears in more than one declared split.")
            session_to_split[str(session)] = split_name
    assigned = frame["session_id"].astype(str).map(session_to_split)
    if assigned.isna().any():
        missing = sorted(frame.loc[assigned.isna(), "session_id"].astype(str).unique())
        raise ValueError(f"Sessions are missing from the declared splits: {missing}")
    return assigned


def _cross_split_duplicates(
    fingerprints: pd.Series, split_names: pd.Series
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    fingerprint_sets = {
        name: set(fingerprints.loc[split_names == name].astype("uint64").tolist())
        for name in ("train", "validation", "test")
    }
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        intersection = fingerprint_sets[left] & fingerprint_sets[right]
        right_rows = fingerprints.loc[split_names == right]
        result[f"{left}_vs_{right}"] = {
            "shared_unique_feature_vectors": len(intersection),
            "right_rows_seen_in_left_fraction": (
                float(right_rows.isin(fingerprint_sets[left]).mean()) if len(right_rows) else 0.0
            ),
        }
    return result


def _window_overlap(frame: pd.DataFrame) -> dict[str, float | int]:
    required = {"session_id", "window_start_seconds", "window_end_seconds"}
    if not required.issubset(frame.columns):
        return {"adjacent_pairs": 0, "overlapping_pairs": 0, "overlap_fraction": 0.0}
    pairs = 0
    overlaps = 0
    for _, session in frame.sort_values(
        ["session_id", "window_start_seconds"]
    ).groupby("session_id"):
        starts = session["window_start_seconds"].to_numpy(dtype=float)
        ends = session["window_end_seconds"].to_numpy(dtype=float)
        if len(session) < 2:
            continue
        pairs += len(session) - 1
        overlaps += int(np.sum(starts[1:] < ends[:-1]))
    return {
        "adjacent_pairs": pairs,
        "overlapping_pairs": overlaps,
        "overlap_fraction": float(overlaps / pairs) if pairs else 0.0,
    }


def audit_predictive_dataset(
    frame: pd.DataFrame,
    *,
    feature_columns: list[str],
    splits: dict[str, list[str]],
) -> dict[str, Any]:
    """Describe leakage risks and limitations without changing official rows."""

    required = {"session_id", "target", "target_code"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Predictive dataset is missing: {sorted(required - set(frame.columns))}")
    fingerprints = _feature_fingerprints(frame, feature_columns)
    split_names = _split_for_sessions(frame, splits)
    missing, non_finite = _missing_and_non_finite(frame, feature_columns)
    session_targets = (
        frame.groupby("session_id")["target_code"].mean().ge(0.5).map(
            {False: "maintain", True: "downgrade_needed"}
        )
    )
    pure_sessions = int(frame.groupby("session_id")["target"].nunique().eq(1).sum())
    overlap = _window_overlap(frame)
    duplicate_rows = int(len(frame) - fingerprints.nunique())
    cross_split = _cross_split_duplicates(fingerprints, split_names)

    warnings: list[dict[str, str]] = []
    if duplicate_rows:
        warnings.append({
            "code": "duplicate_feature_vectors",
            "severity": "high",
            "message": "Varias ventanas contienen entradas idénticas; las métricas deben reportarse por sesión y los splits deben permanecer agrupados.",
        })
    if overlap["overlap_fraction"] > 0.5:
        warnings.append({
            "code": "high_window_overlap",
            "severity": "high",
            "message": "La mayoría de las ventanas adyacentes se solapan; su cantidad no representa observaciones independientes.",
        })
    if any(
        item["shared_unique_feature_vectors"]
        for item in cross_split.values()
    ):
        warnings.append({
            "code": "cross_split_feature_overlap",
            "severity": "high",
            "message": "Existen vectores idénticos entre splits aunque las sesiones estén separadas.",
        })
    class_counts = frame["target"].value_counts()
    if len(class_counts) < 2 or float(class_counts.min() / class_counts.sum()) < 0.15:
        warnings.append({
            "code": "class_imbalance",
            "severity": "high",
            "message": "La clase minoritaria representa menos del 15% de las ventanas; deben usarse métricas por clase y balanceadas.",
        })
    constant = _constant_features(frame, feature_columns)
    if constant:
        warnings.append({
            "code": "constant_features",
            "severity": "medium",
            "message": f"Estas variables son constantes y no discriminan en el dataset actual: {', '.join(constant)}.",
        })

    return {
        "dataset": "predictive",
        "rows": len(frame),
        "sessions": int(frame["session_id"].nunique()),
        "class_distribution_windows": _class_distribution(frame["target"]),
        "class_distribution_sessions": _class_distribution(session_targets),
        "pure_label_sessions": pure_sessions,
        "unique_feature_vectors": int(fingerprints.nunique()),
        "duplicate_feature_rows": duplicate_rows,
        "duplicate_feature_fraction": float(duplicate_rows / len(frame)) if len(frame) else 0.0,
        "constant_features": constant,
        "missing_by_feature": missing,
        "non_finite_by_feature": non_finite,
        "window_overlap": overlap,
        "cross_split_feature_overlap": cross_split,
        "split_session_counts": {
            str(name): int(group["session_id"].nunique())
            for name, group in frame.assign(_split=split_names).groupby("_split")
        },
        "warnings": warnings,
    }


def audit_reactive_dataset(
    frame: pd.DataFrame,
    *,
    feature_columns: list[str],
) -> dict[str, Any]:
    required = {"session_id", "split", "target"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Reactive dataset is missing: {sorted(required - set(frame.columns))}")
    fingerprints = _feature_fingerprints(frame, feature_columns)
    missing, non_finite = _missing_and_non_finite(frame, feature_columns)
    split_sessions = {
        name: set(group["session_id"].astype(str))
        for name, group in frame.groupby("split")
    }
    leakage = {
        f"{left}_vs_{right}": sorted(split_sessions.get(left, set()) & split_sessions.get(right, set()))
        for left, right in (("train", "validation"), ("train", "test"), ("validation", "test"))
    }
    return {
        "dataset": "reactive",
        "rows": len(frame),
        "sessions": int(frame["session_id"].nunique()),
        "class_distribution": _class_distribution(frame["target"]),
        "split_rows": {str(key): int(value) for key, value in frame["split"].value_counts().items()},
        "split_session_overlap": leakage,
        "unique_feature_vectors": int(fingerprints.nunique()),
        "duplicate_feature_rows": int(len(frame) - fingerprints.nunique()),
        "constant_features": _constant_features(frame, feature_columns),
        "missing_by_feature": missing,
        "non_finite_by_feature": non_finite,
        "warnings": [{
            "code": "pseudo_label_target",
            "severity": "medium",
            "message": "El target es una pseudoetiqueta derivada de reglas; una métrica casi perfecta no demuestra por sí sola una mejora real de QoE.",
        }],
    }
