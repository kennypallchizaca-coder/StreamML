"""Build the official StreamML reactive dataset from RTR-NetzTest data."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.streamml.services.release import sha256_file, utc_now_iso, write_json


REACTIVE_FEATURES = ["upload_mbps", "download_mbps", "latency_ms"]
REACTIVE_CLASSES = ["low", "medium", "high"]
PROFILE_TO_CODE = {"low": 1, "medium": 2, "high": 3}
PROFILE_CAPACITY_MBPS = {"low": 1.35, "medium": 3.375, "high": 6.75}


def reactive_target(upload_mbps: pd.Series, latency_ms: pd.Series) -> np.ndarray:
    """Pseudo-label the recommended profile from upload capacity and latency."""

    target = np.where(
        upload_mbps >= PROFILE_CAPACITY_MBPS["high"],
        "high",
        np.where(upload_mbps >= PROFILE_CAPACITY_MBPS["medium"], "medium", "low"),
    )
    target = np.where(latency_ms > 300.0, "low", target)
    target = np.where((latency_ms > 150.0) & (target == "high"), "medium", target)
    return target


def _split_by_session_time(frame: pd.DataFrame) -> pd.Series:
    sessions = (
        frame[["session_id", "timestamp_utc"]]
        .drop_duplicates("session_id")
        .sort_values(["timestamp_utc", "session_id"])["session_id"]
        .tolist()
    )
    total = len(sessions)
    train_count = int(round(total * 0.60))
    validation_count = int(round(total * 0.20))
    mapping: dict[str, str] = {}
    mapping.update({session: "train" for session in sessions[:train_count]})
    mapping.update({session: "validation" for session in sessions[train_count : train_count + validation_count]})
    mapping.update({session: "test" for session in sessions[train_count + validation_count :]})
    return frame["session_id"].map(mapping)


def build_reactive_dataset(root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    source_path = root / "data" / "raw" / "reactive" / "netztest-opendata_hours-048.csv"
    if not source_path.exists():
        raise FileNotFoundError(
            "Reactive raw source is missing. Restore data/raw/reactive from the official source before rebuilding."
        )
    else:
        raw = pd.read_csv(source_path)
        raw["source_file"] = source_path.relative_to(root).as_posix()

    required = {"open_test_uuid", "time_utc", "upload_kbit", "download_kbit", "ping_ms"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"Reactive source is missing required columns: {missing}")

    frame = pd.DataFrame(
        {
            "source_dataset": "RTR-NetzTest Open Data",
            "source_version": "hours-048 export",
            "session_id": raw["open_test_uuid"].astype(str),
            "timestamp_utc": pd.to_datetime(raw["time_utc"], utc=True, errors="coerce"),
            "provenance": raw["source_file"].astype(str),
            "upload_mbps": pd.to_numeric(raw["upload_kbit"], errors="coerce") / 1000.0,
            "download_mbps": pd.to_numeric(raw["download_kbit"], errors="coerce") / 1000.0,
            "latency_ms": pd.to_numeric(raw["ping_ms"], errors="coerce"),
            "upload_unit": "Mbps",
            "download_unit": "Mbps",
            "latency_unit": "ms",
            "target_is_pseudo_label": True,
        }
    )
    frame = frame.dropna(subset=["session_id", "timestamp_utc", *REACTIVE_FEATURES])
    frame = frame.loc[(frame[REACTIVE_FEATURES] >= 0).all(axis=1)].copy()
    frame["target"] = reactive_target(frame["upload_mbps"], frame["latency_ms"])
    frame["target_code"] = frame["target"].map(PROFILE_TO_CODE).astype(int)
    frame["split"] = _split_by_session_time(frame)
    frame = frame.sort_values(["timestamp_utc", "session_id"]).reset_index(drop=True)

    splits = {
        split: sorted(frame.loc[frame["split"] == split, "session_id"].unique().tolist())
        for split in ["train", "validation", "test"]
    }
    discarded_rows = int(len(raw) - len(frame))
    statistics = {
        "dataset": "reactive_dataset",
        "created_at_utc": utc_now_iso(),
        "source_file": source_path.relative_to(root).as_posix(),
        "source_sha256": sha256_file(source_path),
        "rows": int(len(frame)),
        "sessions": int(frame["session_id"].nunique()),
        "features": REACTIVE_FEATURES,
        "target": "target",
        "target_definition": (
            "Pseudo-label: high when upload >= 6.75 Mbps, medium when upload >= 3.375 Mbps, "
            "otherwise low; latency > 300 ms forces low and latency > 150 ms caps high to medium."
        ),
        "class_distribution": frame["target"].value_counts().to_dict(),
        "split_rows": frame["split"].value_counts().to_dict(),
        "split_class_distribution": {
            split: frame.loc[frame["split"] == split, "target"].value_counts().to_dict()
            for split in ["train", "validation", "test"]
        },
        "splits": splits,
        "units": {"upload_mbps": "Mbps", "download_mbps": "Mbps", "latency_ms": "ms"},
        "discarded_rows": discarded_rows,
        "discard_reasons": dict(Counter({"missing_or_invalid_required_values": discarded_rows})),
        "synthetic_data_used": False,
    }
    return frame, statistics


def update_source_manifest(root: Path, reactive_statistics: dict[str, Any]) -> None:
    manifest_path = root / "data" / "raw" / "source_manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["reactive_source"] = {
        "dataset_name": "RTR-NetzTest Open Data",
        "authors": ["Rundfunk und Telekom Regulierungs-GmbH"],
        "doi": None,
        "license": "Open data publication, see bundled LIZENZ.txt",
        "version": reactive_statistics["source_file"],
        "url": "https://www.netztest.at/en/Opendata",
        "files_used": [
            {
                "path": reactive_statistics["source_file"],
                "sha256": reactive_statistics["source_sha256"],
            }
        ],
        "variables_used": {
            "upload_kbit": "converted to upload_mbps",
            "download_kbit": "converted to download_mbps",
            "ping_ms": "renamed to latency_ms",
            "open_test_uuid": "session_id",
            "time_utc": "timestamp_utc",
        },
        "variables_discarded": [
            "location details",
            "device model",
            "network identifiers",
            "server metadata",
            "radio-only metadata",
        ],
        "transformations": reactive_statistics["target_definition"],
    }
    manifest["official_sources"] = {
        "reactive": "RTR-NetzTest Open Data",
        "predictive": manifest.get("dataset_name", "YouTube mobile streaming figshare"),
    }
    write_json(manifest_path, manifest)


def write_dataset_card(root: Path, statistics: dict[str, Any]) -> None:
    card = f"""# Dataset Card: reactive_dataset

## Fuente

- Dataset: RTR-NetzTest Open Data.
- Archivo usado: `{statistics["source_file"]}`.
- SHA-256: `{statistics["source_sha256"]}`.
- Datos sinteticos: no.

## Semantica

Cada fila representa una medicion real de red. `open_test_uuid` se conserva como `session_id`
porque el dataset reactivo es puntual y no contiene ventanas temporales largas por prueba.

## Variables de entrada

- `upload_mbps` (Mbps): subida medida por RTR.
- `download_mbps` (Mbps): descarga medida por RTR.
- `latency_ms` (ms): latencia medida por RTR.

## Target

`target` es una pseudoetiqueta `low`, `medium` o `high`: {statistics["target_definition"]}

## Tamano y particiones

- Filas: {statistics["rows"]}
- Sesiones: {statistics["sessions"]}
- Distribucion: {statistics["class_distribution"]}
- Filas por split: {statistics["split_rows"]}
"""
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports" / "reactive_dataset_card.md").write_text(card, encoding="utf-8")
