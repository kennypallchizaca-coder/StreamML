"""Shared helpers for the official StreamML release."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)


RELEASE_VERSION = "2.0.0"
RANDOM_STATE = 42


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, labels: list[Any]) -> dict[str, Any]:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=labels,
        zero_division=0,
    )
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision_by_class": {str(label): float(precision[index]) for index, label in enumerate(labels)},
        "recall_by_class": {str(label): float(recall[index]) for index, label in enumerate(labels)},
        "f1_by_class": {str(label): float(f1[index]) for index, label in enumerate(labels)},
        "support_by_class": {str(label): int(support[index]) for index, label in enumerate(labels)},
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).astype(int).tolist(),
        "labels": [str(label) for label in labels],
    }


def requirements_snapshot() -> str:
    packages = [
        "pandas",
        "numpy",
        "scikit-learn",
        "joblib",
        "matplotlib",
        "pytest",
    ]
    lines: list[str] = []
    for package in packages:
        try:
            lines.append(f"{package}=={importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            lines.append(f"{package}==not-installed")
    return "\n".join(lines) + "\n"


def file_hashes(paths: list[Path], root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): sha256_file(path) for path in paths if path.exists()}

