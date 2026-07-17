"""Train the official StreamML reactive model."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from src.streamml.data.reactive_dataset import REACTIVE_CLASSES, REACTIVE_FEATURES, PROFILE_TO_CODE
from src.streamml.services.release import classification_metrics, requirements_snapshot, sha256_file, write_json


def load_contract(root: Path) -> dict[str, Any]:
    return json.loads(
        (root / "src" / "streamml" / "config" / "reactive_feature_contract.json").read_text(
            encoding="utf-8"
        )
    )


def subset(frame: pd.DataFrame, split: str, contract: dict[str, Any]) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    selected = frame.loc[frame["split"] == split].copy()
    features = contract["features"]
    return (
        selected.loc[:, features],
        selected["target"].astype(str).to_numpy(),
        selected["session_id"].astype(str).to_numpy(),
    )


def model_definitions(random_state: int) -> dict[str, tuple[Any, dict[str, list[Any]]]]:
    return {
        "DummyClassifier": (DummyClassifier(strategy="most_frequent"), {}),
        "LogisticRegression": (
            Pipeline(
                [
                    ("scaler", StandardScaler()),
                    (
                        "model",
                        LogisticRegression(
                            class_weight="balanced",
                            max_iter=3000,
                            random_state=random_state,
                        ),
                    ),
                ]
            ),
            {"model__C": [0.1, 1.0, 10.0]},
        ),
        "DecisionTreeClassifier": (
            DecisionTreeClassifier(class_weight="balanced", random_state=random_state),
            {"max_depth": [3, 5, 8, None], "min_samples_leaf": [2, 10, 30]},
        ),
        "RandomForestClassifier": (
            RandomForestClassifier(
                n_estimators=300,
                class_weight="balanced",
                random_state=random_state,
                n_jobs=-1,
            ),
            {"max_depth": [5, 10, None], "min_samples_leaf": [1, 5, 20]},
        ),
    }


def fit_models(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    groups_train: np.ndarray,
    X_validation: pd.DataFrame,
    y_validation: np.ndarray,
    random_state: int,
) -> tuple[str, Any, dict[str, Any]]:
    folds = min(5, len(np.unique(groups_train)))
    if folds < 2:
        raise ValueError("Reactive training requires at least two training sessions.")
    group_cv = GroupKFold(n_splits=folds)
    comparisons: dict[str, Any] = {}
    fitted: dict[str, Any] = {}
    for name, (estimator, grid) in model_definitions(random_state).items():
        if grid:
            search = GridSearchCV(
                estimator,
                grid,
                scoring="f1_macro",
                cv=group_cv,
                n_jobs=-1,
                refit=True,
                error_score="raise",
            )
            search.fit(X_train, y_train, groups=groups_train)
            model = search.best_estimator_
            best_score = float(search.best_score_)
            params = search.best_params_
        else:
            model = estimator.fit(X_train, y_train)
            best_score = None
            params = {}
        validation_pred = model.predict(X_validation)
        comparisons[name] = {
            "best_parameters": params,
            "train_groupkfold_macro_f1": best_score,
            "validation": classification_metrics(y_validation, validation_pred, REACTIVE_CLASSES),
        }
        fitted[name] = model
    selected_name = max(
        comparisons,
        key=lambda name: (
            comparisons[name]["validation"]["macro_f1"],
            comparisons[name]["validation"]["balanced_accuracy"],
        ),
    )
    return selected_name, fitted[selected_name], comparisons


def train_reactive_release(root: Path) -> dict[str, Any]:
    dataset_path = root / "data" / "processed" / "reactive_dataset.csv"
    frame = pd.read_csv(dataset_path)
    contract = load_contract(root)
    if contract["features"] != REACTIVE_FEATURES:
        raise ValueError("Reactive feature contract does not match REACTIVE_FEATURES.")

    splits = {
        split: sorted(frame.loc[frame["split"] == split, "session_id"].astype(str).unique().tolist())
        for split in ["train", "validation", "test"]
    }
    if (
        set(splits["train"]) & set(splits["validation"])
        or set(splits["train"]) & set(splits["test"])
        or set(splits["validation"]) & set(splits["test"])
    ):
        raise ValueError("Reactive sessions are not disjoint.")

    X_train, y_train, groups_train = subset(frame, "train", contract)
    X_validation, y_validation, _ = subset(frame, "validation", contract)
    X_test, y_test, _ = subset(frame, "test", contract)
    for split, labels in [("train", y_train), ("validation", y_validation), ("test", y_test)]:
        if set(labels) != set(REACTIVE_CLASSES):
            raise RuntimeError(f"Reactive {split} split does not contain all classes.")

    selected_name, selected_model, comparisons = fit_models(
        X_train,
        y_train,
        groups_train,
        X_validation,
        y_validation,
        int(contract["random_state"]),
    )
    X_train_validation = pd.concat([X_train, X_validation], ignore_index=True)
    y_train_validation = np.concatenate([y_train, y_validation])
    final_model = clone(selected_model).fit(X_train_validation, y_train_validation)
    test_pred = final_model.predict(X_test)
    test_metrics = classification_metrics(y_test, test_pred, REACTIVE_CLASSES)

    baseline = DummyClassifier(strategy="most_frequent").fit(X_train_validation, y_train_validation)
    baseline_pred = baseline.predict(X_test)
    baseline_metrics = classification_metrics(y_test, baseline_pred, REACTIVE_CLASSES)
    validation_metrics = comparisons[selected_name]["validation"]

    release_dir = root / "models" / "registry" / "reactive"
    release_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, release_dir / "model.joblib")
    shutil.copyfile(
        root / "src" / "streamml" / "config" / "reactive_feature_contract.json",
        release_dir / "feature_contract.json",
    )
    shutil.copyfile(root / "data" / "raw" / "source_manifest.json", release_dir / "source_manifest.json")
    write_json(release_dir / "class_mapping.json", PROFILE_TO_CODE)
    (release_dir / "requirements_snapshot.txt").write_text(requirements_snapshot(), encoding="utf-8")

    manifest = {
        "release_version": "2.0.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_role": "reactive",
        "model_path": "models/registry/reactive/model.joblib",
        "dataset_path": "data/processed/reactive_dataset.csv",
        "dataset_sha256": sha256_file(dataset_path),
        "split_method": "chronological split by session_id/open_test_uuid",
        "splits": splits,
        "split_rows": frame["split"].value_counts().to_dict(),
        "features": REACTIVE_FEATURES,
        "feature_count": len(REACTIVE_FEATURES),
        "classes": REACTIVE_CLASSES,
        "class_mapping": PROFILE_TO_CODE,
        "target": "target",
        "target_is_pseudo_label": True,
        "selected_model": selected_name,
        "selected_with": "validation Macro F1 and balanced accuracy",
        "selected_parameters": comparisons[selected_name]["best_parameters"],
    }
    results = {
        "dataset": {
            "rows": int(len(frame)),
            "sessions": int(frame["session_id"].nunique()),
            "class_distribution": frame["target"].value_counts().to_dict(),
            "split_rows": frame["split"].value_counts().to_dict(),
        },
        "model_comparison": comparisons,
        "selected_model": selected_name,
        "validation": validation_metrics,
        "test": test_metrics,
        "baseline": {"model": "DummyClassifier(strategy='most_frequent')", "test": baseline_metrics},
        "generalization_gap": float(validation_metrics["macro_f1"] - test_metrics["macro_f1"]),
        "improvement_over_baseline_test_macro_f1": float(
            test_metrics["macro_f1"] - baseline_metrics["macro_f1"]
        ),
        "statuses": {
            "official_release": True,
            "reactive_model_ready": True,
        },
    }
    write_json(release_dir / "training_manifest.json", manifest)
    write_json(release_dir / "metrics.json", results)

    return results
