"""Vistas de telemetría seguras y disponibilidad de características (features)."""

from __future__ import annotations

from datetime import datetime
from typing import Any


INSUFFICIENT_DATA = "Datos insuficientes para una predicción válida"


def _timestamp(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def vdo_phone_status(
    phone: dict[str, Any] | None,
    reference_at: str | None = None,
    *,
    freshness_seconds: float = 10.0,
) -> str | None:
    """Return a usable phone state without treating an old browser sample as current."""

    if not phone:
        return None
    observed = _timestamp(phone.get("observed_at"))
    reference = _timestamp(reference_at)
    if observed is None:
        return None
    if reference is not None and (reference - observed > freshness_seconds or observed - reference > 5.0):
        return "stale"
    status = phone.get("status")
    return status if status in {"waiting", "connected", "disconnected", "error"} else None


def merge_vdo_network(
    network: dict[str, Any] | None,
    phone: dict[str, Any] | None,
    reference_at: str,
) -> dict[str, Any] | None:
    """Prefer fresh phone-path WebRTC measurements while retaining probe-only fields."""

    merged = dict(network or {})
    if phone is None:
        return merged or None
    if vdo_phone_status(phone, reference_at) != "connected":
        # Once a mobile reporter exists, a stale/disconnected phone must not be
        # replaced by the server computer's usually stable home connection.
        return None
    metrics = phone.get("metrics") or {}
    merged.pop("upload_mbps", None)
    merged.pop("connection_capacity_mbps", None)
    merged["source"] = "vdo_ninja_webrtc_partial"
    outgoing = metrics.get("available_outgoing_bitrate_kbps")
    received = metrics.get("bitrate_kbps")
    capacity_kbps = outgoing if outgoing is not None and float(outgoing) > 0 else received
    if capacity_kbps is not None and float(capacity_kbps) > 0:
        capacity_mbps = float(capacity_kbps) / 1000.0
        merged["upload_mbps"] = capacity_mbps
        merged["connection_capacity_mbps"] = capacity_mbps
        merged["source"] = "vdo_ninja_webrtc_hybrid"
    if metrics.get("round_trip_time_ms") is not None:
        merged["latency_ms"] = float(metrics["round_trip_time_ms"])
        merged["source"] = "vdo_ninja_webrtc_hybrid"
    if metrics.get("jitter_ms") is not None:
        merged["jitter_ms"] = float(metrics["jitter_ms"])
    if metrics.get("packet_loss_percent") is not None:
        merged["packet_loss_percent"] = float(metrics["packet_loss_percent"])
    return merged or None


def feature_availability(metrics: dict[str, Any], network: dict[str, Any] | None = None) -> dict[str, dict[str, bool]]:
    network = network or {}
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
            "upload_mbps": network.get("upload_mbps") is not None,
            "download_mbps": network.get("download_mbps") is not None,
            "latency_ms": network.get("latency_ms") is not None,
        },
        "predictive_model": {
            "connection_capacity_history_mbps": network.get("connection_capacity_mbps") is not None,
            "current_profile": network.get("current_profile") is not None,
        },
    }


def telemetry_snapshot(
    record: dict[str, Any] | None,
    registry: Any,
    phone: dict[str, Any] | None = None,
    *,
    reference_at: str | None = None,
) -> dict[str, Any] | None:
    if not record and not phone:
        return None
    record = record or {}
    metrics = record.get("metrics", {})
    network = record.get("network") or {}
    phone_metrics = (phone or {}).get("metrics") or {}
    phone_status = vdo_phone_status(phone, reference_at or record.get("observed_at"))
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
            features.append(
                {
                    "name": name,
                    "state": (
                        "available"
                        if name in {"upload_mbps", "download_mbps", "latency_ms"} and network.get(name) is not None
                        else "missing"
                    ),
                    "unit": metadata.get("unit"),
                    "reason": (
                        "OBS WebSocket no proporciona esta medición compatible."
                        if role == "reactive"
                        else "No existe una ventana de capacidad de red compatible de 600 segundos."
                    ),
                }
            )

    phone_bitrate = phone_metrics.get("bitrate_kbps")
    phone_available = phone_metrics.get("available_outgoing_bitrate_kbps")
    return {
        "captured_at": record.get("observed_at"),
        "phone_status": phone_status,
        "phone_captured_at": (phone or {}).get("observed_at"),
        "phone_bitrate_kbps": phone_bitrate if phone_bitrate and float(phone_bitrate) > 0 else None,
        "phone_available_bitrate_kbps": (phone_available if phone_available and float(phone_available) > 0 else None),
        "phone_fps": phone_metrics.get("frames_per_second"),
        "obs_status": obs_status,
        "mediamtx_status": "connected" if metrics.get("stream_active") else "idle",
        "stream_active": metrics.get("stream_active"),
        "stream_reconnecting": metrics.get("stream_reconnecting"),
        "bitrate_kbps": metrics.get("output_bitrate_kbps"),
        "fps": metrics.get("active_fps"),
        "dropped_frames": metrics.get("output_skipped_frames"),
        "packet_loss_percent": network.get("packet_loss_percent"),
        "latency_ms": network.get("latency_ms"),
        "jitter_ms": network.get("jitter_ms"),
        "upload_mbps": network.get("upload_mbps"),
        "download_mbps": network.get("download_mbps"),
        "connection_capacity_mbps": network.get("connection_capacity_mbps"),
        "network_source": network.get("source"),
        "current_profile": network.get("current_profile"),
        "features": features,
    }
