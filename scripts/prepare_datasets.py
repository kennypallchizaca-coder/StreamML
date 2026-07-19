"""Prepare the official reactive and predictive training datasets from local raw data."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.streamml.data.dataset_builder import build_dataset, build_schema, write_json
from src.streamml.data.reactive_dataset import build_reactive_dataset, update_source_manifest, write_dataset_card


def main() -> None:
    config = json.loads(
        (ROOT / "src" / "streamml" / "config" / "dataset_config.json").read_text(encoding="utf-8")
    )
    manifest_path = ROOT / config["paths"]["source_manifest"]
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing source manifest: {manifest_path.relative_to(ROOT)}")
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    reactive, reactive_stats = build_reactive_dataset(ROOT)
    reactive_path = ROOT / "data" / "processed" / "reactive_dataset.csv"
    reactive_path.parent.mkdir(parents=True, exist_ok=True)
    reactive.to_csv(reactive_path, index=False)
    update_source_manifest(ROOT, reactive_stats)
    write_dataset_card(ROOT, reactive_stats)
    write_json(ROOT / "data" / "interim" / "reactive_dataset_statistics.json", reactive_stats)

    predictive, predictive_stats = build_dataset(ROOT, config, source_manifest)
    predictive_path = ROOT / config["paths"]["processed_dataset"]
    predictive.to_csv(predictive_path, index=False)
    write_json(ROOT / config["paths"]["build_statistics"], predictive_stats)
    write_json(ROOT / config["paths"]["dataset_schema"], build_schema(predictive))

    print(json.dumps({
        "reactive": {"path": reactive_path.relative_to(ROOT).as_posix(), "rows": len(reactive)},
        "predictive": {"path": predictive_path.relative_to(ROOT).as_posix(), "rows": len(predictive)},
    }, indent=2))


if __name__ == "__main__":
    main()
