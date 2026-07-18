"""Compare fixed, reactive and full control on a recorded or demo replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.streamml.evaluation.control_replay import (
    ReplaySample,
    demonstration_samples,
    replay_control_strategies,
)
from src.streamml.services.release import write_json, write_text_lf


def _markdown(report: dict, source: str) -> str:
    strategies = report["strategies"]
    lines = [
        "# Replay reproducible del controlador",
        "",
        f"**Fuente:** {source}",
        "",
        "> Este resultado es un proxy de ingeniería. No sustituye una prueba física de QoE con teléfono, OBS y una red degradada.",
        "",
        "| Estrategia | Score proxy | Interrupción | Respaldo | Cambios de perfil |",
        "|---|---:|---:|---:|---:|",
    ]
    labels = {
        "fixed_profile": "Perfil fijo",
        "reactive_only": "Solo reactivo",
        "reactive_predictive_agent": "Reactivo + predictivo + agente",
    }
    for name, values in strategies.items():
        lines.append(
            f"| {labels[name]} | {values['qoe_proxy_score']:.2f} | "
            f"{values['interruption_seconds']:.1f} s | {values['backup_seconds']:.1f} s | "
            f"{values['profile_switches']} |"
        )
    lines.extend([
        "",
        f"El sistema completo mejora **{report['full_agent_improvement_over_fixed_points']:.2f} puntos** sobre el perfil fijo en este replay.",
        "",
        "## Eventos del agente",
        "",
    ])
    for event in strategies["reactive_predictive_agent"]["events"]:
        lines.append(
            f"- t={event['observed_at']:.0f}s · `{event['action']}` · "
            f"{event['from']} → {event['to']} · `{event['reason_code']}` · {event['reason']}"
        )
    lines.append("")
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="Optional JSON array of recorded ReplaySample-compatible observations.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.input:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Replay input must be a JSON array.")
        samples = [ReplaySample.from_dict(item) for item in raw]
        source = f"telemetría registrada: {args.input}"
    else:
        samples = demonstration_samples()
        source = "escenario demostrativo determinista (sintético; no es evidencia de campo)"
    report = replay_control_strategies(samples)
    report["source"] = source
    write_json(ROOT / "reports" / "control_replay.json", report)
    write_text_lf(ROOT / "reports" / "control_replay.md", _markdown(report, source))
    print(json.dumps({
        name: {
            "qoe_proxy_score": round(values["qoe_proxy_score"], 2),
            "interruption_seconds": values["interruption_seconds"],
            "profile_switches": values["profile_switches"],
        }
        for name, values in report["strategies"].items()
    }, indent=2))


if __name__ == "__main__":
    main()
