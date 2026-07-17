"""Customer-safe telemetry views and feature availability."""

from __future__ import annotations

from typing import Any


INSUFFICIENT_DATA = "Datos insuficientes para una predicción válida"


def feature_availability(metrics: dict[str, Any]) -> dict[str, dict[str, bool]]:
    return {
        "dashboard": {
            "obs_connected": metrics.get("obs_connected") is not None,
            "stream_active": metrics.get("stream_active") is not None,
            "active_fps": metrics.get("active_fps") is not None,
            "frames_skipped": metrics.get("output_skipped_frames") is not None,
            "output_bitrate_kbps": metrics.get("output_bitrate_kbps") is not None,
            "output_congestion": metrics.get("output_congestion") is not None,
        },
        "reactive_model": {
            "upload_mbps": False,
            "download_mbps": False,
            "latency_ms": False,
        },
        "predictive_model": {
            "connection_capacity_history_mbps": False,
            "current_profile": False,
        },
    }


def telemetry_snapshot(record: dict[str, Any] | None, registry: Any) -> dict[str, Any] | None:
    if not record:
        return None
    metrics = record.get("metrics", {})
    if metrics.get("stream_reconnecting"):
        obs_status = "reconnecting"
    elif metrics.get("obs_connected") is True:
        obs_status = "connected"
    elif metrics.get("obs_connected") is False:
        obs_status = "disconnected"
    else:
        obs_status = None

    features = []
    for role in ("reactive", "predictive"):
        contract = registry.contracts[role]
        for name in contract["features"]:
            metadata = contract.get("feature_metadata", {}).get(name, {})
            features.append({
                "name": name,
                "state": "missing",
                "unit": metadata.get("unit"),
                "reason": (
                    "OBS WebSocket no proporciona esta medición compatible."
                    if role == "reactive"
                    else "No existe una ventana de capacidad de red compatible de 120 segundos."
                ),
            })

    return {
        "captured_at": record.get("observed_at"),
        "phone_status": None,
        "obs_status": obs_status,
        "mediamtx_status": None,
        "bitrate_kbps": metrics.get("output_bitrate_kbps"),
        "fps": metrics.get("active_fps"),
        "dropped_frames": metrics.get("output_skipped_frames"),
        "packet_loss_percent": None,
        "latency_ms": None,
        "current_profile": None,
        "features": features,
    }
