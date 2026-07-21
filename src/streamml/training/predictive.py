"""Selección de modelos agrupados y evaluación honesta para el modelo predictivo de StreamML."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
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
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from src.streamml.features.predictive_features import FEATURE_COLUMNS, frame_in_contract_order, load_feature_contract
from src.streamml.services.release import write_json, write_text_lf


CLASS_NAMES = ["maintain", "downgrade_needed"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_sessions(frame: pd.DataFrame, config: dict) -> dict[str, list[str]]:
    sessions = sorted(frame["session_id"].astype(str).unique())
    if len(sessions) < 10:
        raise ValueError("At least 10 sessions are required for grouped train/validation/test splits.")
    rng = np.random.default_rng(int(config["random_state"]))
    # Stratify at session level, never at row/window level.  A session label is
    # its majority target; this keeps rare maintain-only sessions represented
    # in every split without leaking adjacent windows across boundaries.
    session_labels = frame.groupby("session_id")["target_code"].mean().ge(0.5).astype(int).to_dict()
    by_label = {
        label: np.array([session for session in sessions if session_labels[session] == label]) for label in (0, 1)
    }
    if any(len(group) < 3 for group in by_label.values()):
        raise ValueError("At least three sessions per majority target are required.")
    result: dict[str, list[str]] = {"train": [], "validation": [], "test": []}
    for group in by_label.values():
        shuffled = rng.permutation(group)
        validation_count = max(1, int(round(len(group) * float(config["split"]["validation_fraction"]))))
        test_count = max(1, int(round(len(group) * float(config["split"]["test_fraction"]))))
        if validation_count + test_count >= len(group):
            raise ValueError("Configured grouped split leaves no training sessions.")
        train_count = len(group) - validation_count - test_count
        result["train"].extend(shuffled[:train_count].tolist())
        result["validation"].extend(shuffled[train_count : train_count + validation_count].tolist())
        result["test"].extend(shuffled[train_count + validation_count :].tolist())
    return {name: sorted(values) for name, values in result.items()}


def assert_disjoint_splits(splits: dict[str, list[str]]) -> None:
    train, validation, test = map(set, (splits["train"], splits["validation"], splits["test"]))
    if train & validation or train & test or validation & test:
        raise ValueError("A session_id appears in more than one split.")


def subset(frame: pd.DataFrame, sessions: list[str], contract: dict) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    selected = frame.loc[frame["session_id"].isin(sessions)].copy()
    return (
        frame_in_contract_order(selected, contract),
        selected["target_code"].to_numpy(dtype=int),
        selected["session_id"].to_numpy(dtype=str),
    )


def positive_probability(model: Any, X: pd.DataFrame) -> np.ndarray:
    probabilities = np.asarray(model.predict_proba(X), dtype=float)
    classes = list(model.classes_)
    if 1 not in classes:
        return np.zeros(len(X), dtype=float)
    return probabilities[:, classes.index(1)]


def classification_metrics(y_true: np.ndarray, probability: np.ndarray, threshold: float) -> dict:
    prediction = (probability >= threshold).astype(int)
    precision, recall, f1, support = precision_recall_fscore_support(y_true, prediction, labels=[0, 1], zero_division=0)
    result = {
        "accuracy": float(accuracy_score(y_true, prediction)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, prediction)),
        "precision_by_class": {name: float(precision[index]) for index, name in enumerate(CLASS_NAMES)},
        "recall_by_class": {name: float(recall[index]) for index, name in enumerate(CLASS_NAMES)},
        "f1_by_class": {name: float(f1[index]) for index, name in enumerate(CLASS_NAMES)},
        "support_by_class": {name: int(support[index]) for index, name in enumerate(CLASS_NAMES)},
        "macro_f1": float(f1_score(y_true, prediction, average="macro", zero_division=0)),
        "recall_downgrade_needed": float(recall_score(y_true, prediction, pos_label=1, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, probability)) if len(np.unique(y_true)) == 2 else None,
        "roc_auc": float(roc_auc_score(y_true, probability)) if len(np.unique(y_true)) == 2 else None,
        "confusion_matrix": confusion_matrix(y_true, prediction, labels=[0, 1]).astype(int).tolist(),
        "false_positives": int(np.sum((prediction == 1) & (y_true == 0))),
        "false_negatives": int(np.sum((prediction == 0) & (y_true == 1))),
        "threshold": float(threshold),
    }
    return result


def choose_threshold(
    y_true: np.ndarray, probability: np.ndarray, model_options: list[float]
) -> tuple[float, list[dict]]:
    table = [classification_metrics(y_true, probability, float(threshold)) for threshold in model_options]
    best_macro = max(item["macro_f1"] for item in table)
    eligible = [item for item in table if item["macro_f1"] >= 0.95 * best_macro]
    chosen = max(
        eligible,
        key=lambda item: (
            item["recall_downgrade_needed"],
            item["macro_f1"],
            -abs(item["threshold"] - 0.5),
        ),
    )
    return float(chosen["threshold"]), table


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
            {"max_depth": [3, 5, 8, None], "min_samples_leaf": [2, 5, 10]},
        ),
        "RandomForestClassifier": (
            RandomForestClassifier(
                n_estimators=300,
                class_weight="balanced",
                random_state=random_state,
                n_jobs=-1,
            ),
            {"max_depth": [5, 10, None], "min_samples_leaf": [1, 3, 5]},
        ),
    }


def grouped_cv_splits(y: np.ndarray, groups: np.ndarray) -> int:
    group_targets = {group: int(np.mean(y[groups == group]) >= 0.5) for group in np.unique(groups)}
    return min(
        5,
        min(sum(value == label for value in group_targets.values()) for label in (0, 1)),
    )


def fit_models(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    groups_train: np.ndarray,
    X_validation: pd.DataFrame,
    y_validation: np.ndarray,
    config: dict,
) -> tuple[str, Any, float, dict]:
    random_state = int(config["random_state"])
    folds = grouped_cv_splits(y_train, groups_train)
    if folds < 2:
        raise ValueError("Stratified grouped CV requires at least two sessions per target.")
    group_cv = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=random_state)
    comparisons: dict[str, dict] = {}
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
            cv_macro_f1 = float(search.best_score_)
            best_params = search.best_params_
        else:
            model = estimator.fit(X_train, y_train)
            cv_macro_f1 = None
            best_params = {}
        probability = positive_probability(model, X_validation)
        threshold, threshold_table = choose_threshold(y_validation, probability, config["threshold_values"])
        metrics = classification_metrics(y_validation, probability, threshold)
        comparisons[name] = {
            "best_parameters": best_params,
            "train_groupkfold_macro_f1": cv_macro_f1,
            "validation": metrics,
            "threshold_search": threshold_table,
        }
        fitted[name] = model

    selected_name = max(
        comparisons,
        key=lambda name: (
            comparisons[name]["validation"]["macro_f1"],
            comparisons[name]["validation"]["recall_downgrade_needed"],
        ),
    )
    selected_model = fitted[selected_name]
    selected_threshold = float(comparisons[selected_name]["validation"]["threshold"])
    return selected_name, selected_model, selected_threshold, comparisons


def bootstrap_macro_f1_by_session(
    y_true: np.ndarray,
    probability: np.ndarray,
    groups: np.ndarray,
    threshold: float,
    random_state: int,
    repetitions: int = 1000,
) -> dict:
    unique_groups = np.unique(groups)
    rng = np.random.default_rng(random_state)
    values: list[float] = []
    for _ in range(repetitions):
        sampled = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        indices = np.concatenate([np.flatnonzero(groups == group) for group in sampled])
        prediction = (probability[indices] >= threshold).astype(int)
        values.append(float(f1_score(y_true[indices], prediction, average="macro", zero_division=0)))
    return {
        "method": "session bootstrap",
        "repetitions": repetitions,
        "confidence_level": 0.95,
        "lower": float(np.percentile(values, 2.5)),
        "upper": float(np.percentile(values, 97.5)),
    }


def feature_importance(model: Any) -> list[dict]:
    estimator = model.named_steps["model"] if isinstance(model, Pipeline) else model
    if hasattr(estimator, "feature_importances_"):
        values = np.asarray(estimator.feature_importances_, dtype=float)
    elif hasattr(estimator, "coef_"):
        values = np.abs(np.asarray(estimator.coef_, dtype=float)[0])
    else:
        return []
    order = np.argsort(values)[::-1]
    return [{"feature": FEATURE_COLUMNS[index], "importance": float(values[index])} for index in order]


def requirements_snapshot() -> str:
    packages = ["pandas", "numpy", "scikit-learn", "joblib", "pytest"]
    return "\n".join(f"{package}=={importlib.metadata.version(package)}" for package in packages) + "\n"


def train_predictive_release(root: Path, config: dict) -> dict:
    dataset_path = root / config["paths"]["processed_dataset"]
    contract_path = root / "src" / "streamml" / "config" / "predictive_feature_contract.json"
    frame = pd.read_csv(dataset_path)
    contract = load_feature_contract(contract_path)
    splits = split_sessions(frame, config)
    assert_disjoint_splits(splits)

    X_train, y_train, groups_train = subset(frame, splits["train"], contract)
    X_validation, y_validation, _ = subset(frame, splits["validation"], contract)
    X_test, y_test, groups_test = subset(frame, splits["test"], contract)
    for name, labels in (("train", y_train), ("validation", y_validation), ("test", y_test)):
        if len(np.unique(labels)) != 2:
            raise RuntimeError(f"The grouped {name} split does not contain both target classes.")

    selected_name, selected_model, threshold, comparisons = fit_models(
        X_train, y_train, groups_train, X_validation, y_validation, config
    )
    X_train_validation = pd.concat([X_train, X_validation], ignore_index=True)
    y_train_validation = np.concatenate([y_train, y_validation])
    final_model = clone(selected_model).fit(X_train_validation, y_train_validation)
    test_probability = positive_probability(final_model, X_test)
    test_metrics = classification_metrics(y_test, test_probability, threshold)

    dummy = DummyClassifier(strategy="most_frequent").fit(X_train_validation, y_train_validation)
    dummy_probability = positive_probability(dummy, X_test)
    baseline_test = classification_metrics(y_test, dummy_probability, 0.5)
    validation_metrics = comparisons[selected_name]["validation"]
    test_metrics["macro_f1_session_bootstrap_95ci"] = bootstrap_macro_f1_by_session(
        y_test,
        test_probability,
        groups_test,
        threshold,
        int(config["random_state"]),
    )

    release_dir = root / config["paths"].get("release_dir", "models/registry/predictive")
    release_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, release_dir / "model.joblib")
    shutil.copyfile(contract_path, release_dir / "feature_contract.json")
    shutil.copyfile(root / config["paths"]["source_manifest"], release_dir / "source_manifest.json")
    write_json(release_dir / "class_mapping.json", {"maintain": 0, "downgrade_needed": 1})
    write_json(
        release_dir / "threshold.json",
        {
            "threshold": threshold,
            "selected_with": "validation only",
            "evaluated_values": config["threshold_values"],
            "policy": "highest downgrade recall among thresholds within 95% of best validation Macro F1",
        },
    )
    write_text_lf(release_dir / "requirements_snapshot.txt", requirements_snapshot())

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "release_version": "3.0.0",
        "model_role": "predictive",
        "model_path": "models/registry/predictive/model.joblib",
        "dataset_path": config["paths"]["processed_dataset"],
        "dataset_sha256": sha256_file(dataset_path),
        "random_state": config["random_state"],
        "split_method": "session_id grouped deterministic permutation; no row-level split",
        "splits": splits,
        "split_window_counts": {
            "train": len(X_train),
            "validation": len(X_validation),
            "test": len(X_test),
        },
        "hyperparameter_selection": "StratifiedGroupKFold within training sessions only",
        "groupkfold_splits": grouped_cv_splits(y_train, groups_train),
        "selected_model": selected_name,
        "selected_parameters": comparisons[selected_name]["best_parameters"],
        "feature_count": len(FEATURE_COLUMNS),
        "features": FEATURE_COLUMNS,
        "target": "target_code",
        "official_release": True,
        "predictive_model_ready": True,
        "validated_with_public_dataset": True,
    }
    results = {
        "dataset": {
            "sessions": int(frame["session_id"].nunique()),
            "windows": len(frame),
            "class_distribution": {str(key): int(value) for key, value in frame["target"].value_counts().items()},
        },
        "model_comparison": comparisons,
        "selected_model": selected_name,
        "threshold": threshold,
        "validation": validation_metrics,
        "test": test_metrics,
        "baseline": {"model": "DummyClassifier(strategy='most_frequent')", "test": baseline_test},
        "generalization_gap": float(validation_metrics["macro_f1"] - test_metrics["macro_f1"]),
        "improvement_over_dummy_test_macro_f1": float(test_metrics["macro_f1"] - baseline_test["macro_f1"]),
        "feature_importance": feature_importance(final_model),
        "statuses": {
            "official_release": True,
            "predictive_model_ready": True,
            "validated_with_public_dataset": True,
        },
    }
    write_json(release_dir / "training_manifest.json", manifest)
    write_json(release_dir / "metrics.json", results)

    return results


def evaluate_saved_release(root: Path, config: dict) -> dict:
    release_dir = root / config["paths"].get("release_dir", "models/registry/predictive")
    frame = pd.read_csv(root / config["paths"]["processed_dataset"])
    contract = load_feature_contract(release_dir / "feature_contract.json")
    manifest = json.loads((release_dir / "training_manifest.json").read_text(encoding="utf-8"))
    threshold = json.loads((release_dir / "threshold.json").read_text(encoding="utf-8"))["threshold"]
    model = joblib.load(release_dir / "model.joblib")
    X_test, y_test, groups_test = subset(frame, manifest["splits"]["test"], contract)
    probability = positive_probability(model, X_test)
    if not np.isfinite(probability).all():
        raise RuntimeError("Model predict_proba returned non-finite values.")
    metrics = classification_metrics(y_test, probability, float(threshold))
    metrics["macro_f1_session_bootstrap_95ci"] = bootstrap_macro_f1_by_session(
        y_test, probability, groups_test, float(threshold), int(config["random_state"])
    )
    saved = json.loads((release_dir / "metrics.json").read_text(encoding="utf-8"))
    if not np.isclose(metrics["macro_f1"], saved["test"]["macro_f1"]):
        raise RuntimeError("Recomputed test Macro F1 differs from the saved training result.")
    saved["test"] = metrics
    saved["evaluation_reloaded_model"] = True
    write_json(release_dir / "metrics.json", saved)
    return saved
