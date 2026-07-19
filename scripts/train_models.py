"""Train and persist both official StreamML models."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.streamml.training.predictive import train_predictive_release
from src.streamml.training.reactive import train_reactive_release


def main() -> None:
    config = json.loads(
        (ROOT / "src" / "streamml" / "config" / "dataset_config.json").read_text(encoding="utf-8")
    )
    reactive = train_reactive_release(ROOT)
    predictive = train_predictive_release(ROOT, config)
    print(json.dumps({
        "reactive": {"model": reactive["selected_model"], "test_macro_f1": reactive["test"]["macro_f1"]},
        "predictive": {"model": predictive["selected_model"], "test_macro_f1": predictive["test"]["macro_f1"]},
    }, indent=2))


if __name__ == "__main__":
    main()
