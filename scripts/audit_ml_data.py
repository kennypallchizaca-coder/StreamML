"""Generate machine-readable and presentation-ready ML dataset evidence."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.streamml.evaluation.data_quality import (
    audit_predictive_dataset,
    audit_reactive_dataset,
)
from src.streamml.features.predictive_features import FEATURE_COLUMNS
from src.streamml.services.release import read_json, write_json, write_text_lf


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _markdown(report: dict) -> str:
    predictive = report["predictive"]
    reactive = report["reactive"]
    lines = [
        "# Auditoría reproducible de datos ML",
        "",
        "Este informe se genera directamente desde los CSV procesados y los splits oficiales. No modifica los datos ni los modelos.",
        "",
        "## Resumen",
        "",
        "| Dataset | Filas/ventanas | Sesiones | Vectores únicos | Filas duplicadas por features |",
        "|---|---:|---:|---:|---:|",
        f"| Reactivo | {reactive['rows']} | {reactive['sessions']} | {reactive['unique_feature_vectors']} | {reactive['duplicate_feature_rows']} |",
        f"| Predictivo | {predictive['rows']} | {predictive['sessions']} | {predictive['unique_feature_vectors']} | {predictive['duplicate_feature_rows']} ({_percent(predictive['duplicate_feature_fraction'])}) |",
        "",
        "## Riesgos y limitaciones detectadas",
        "",
    ]
    for warning in reactive["warnings"] + predictive["warnings"]:
        lines.append(f"- **{warning['severity'].upper()} · {warning['code']}**: {warning['message']}")
    lines.extend([
        "",
        "## Solapamiento predictivo",
        "",
        f"- Ventanas adyacentes solapadas: {predictive['window_overlap']['overlapping_pairs']} de {predictive['window_overlap']['adjacent_pairs']} ({_percent(predictive['window_overlap']['overlap_fraction'])}).",
        f"- Sesiones con una sola clase: {predictive['pure_label_sessions']} de {predictive['sessions']}.",
        "- Los splits son por sesión; el solapamiento de vectores entre splits se reporta como limitación, no se oculta.",
        "",
        "## Interpretación",
        "",
        "Las métricas oficiales deben presentarse junto al baseline, las métricas balanceadas y estas limitaciones. La validación definitiva del objetivo requiere más sesiones móviles independientes y una comparación de QoE bajo degradaciones reales.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    predictive_frame = pd.read_csv(ROOT / "data" / "processed" / "predictive_dataset.csv")
    reactive_frame = pd.read_csv(ROOT / "data" / "processed" / "reactive_dataset.csv")
    predictive_manifest = read_json(
        ROOT / "models" / "registry" / "predictive" / "training_manifest.json"
    )
    reactive_contract = read_json(
        ROOT / "src" / "streamml" / "config" / "reactive_feature_contract.json"
    )
    report = {
        "schema_version": "1.0.0",
        "reactive": audit_reactive_dataset(
            reactive_frame, feature_columns=reactive_contract["features"]
        ),
        "predictive": audit_predictive_dataset(
            predictive_frame,
            feature_columns=FEATURE_COLUMNS,
            splits=predictive_manifest["splits"],
        ),
    }
    write_json(ROOT / "reports" / "ml_data_quality.json", report)
    write_text_lf(ROOT / "reports" / "ml_data_quality.md", _markdown(report))
    print(json.dumps({
        "reactive_rows": report["reactive"]["rows"],
        "predictive_windows": report["predictive"]["rows"],
        "predictive_sessions": report["predictive"]["sessions"],
        "predictive_warnings": len(report["predictive"]["warnings"]),
    }, indent=2))


if __name__ == "__main__":
    main()
