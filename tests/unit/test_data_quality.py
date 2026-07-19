import pandas as pd

from src.streamml.evaluation.data_quality import audit_predictive_dataset


def test_predictive_audit_reports_overlap_duplicates_and_grouped_split_overlap() -> None:
    frame = pd.DataFrame([
        {"session_id": "a", "target": "maintain", "target_code": 0, "start": 0, "end": 10, "x": 1.0},
        {"session_id": "a", "target": "maintain", "target_code": 0, "start": 5, "end": 15, "x": 1.0},
        {"session_id": "b", "target": "downgrade_needed", "target_code": 1, "start": 0, "end": 10, "x": 1.0},
        {"session_id": "c", "target": "maintain", "target_code": 0, "start": 0, "end": 10, "x": 2.0},
    ]).rename(columns={"start": "window_start_seconds", "end": "window_end_seconds"})
    report = audit_predictive_dataset(
        frame,
        feature_columns=["x"],
        splits={"train": ["a"], "validation": ["b"], "test": ["c"]},
    )
    assert report["duplicate_feature_rows"] == 2
    assert report["window_overlap"]["overlapping_pairs"] == 1
    assert report["cross_split_feature_overlap"]["train_vs_validation"]["shared_unique_feature_vectors"] == 1
    assert {warning["code"] for warning in report["warnings"]} >= {
        "duplicate_feature_vectors",
        "cross_split_feature_overlap",
    }
