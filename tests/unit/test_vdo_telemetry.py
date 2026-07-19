from src.streamml.services.telemetry import merge_vdo_network, vdo_phone_status


def test_phone_status_becomes_stale_without_claiming_a_disconnect() -> None:
    phone = {
        "observed_at": "2026-07-17T12:00:00+00:00",
        "status": "connected",
        "metrics": {},
    }
    assert vdo_phone_status(phone, "2026-07-17T12:00:05+00:00") == "connected"
    assert vdo_phone_status(phone, "2026-07-17T12:00:11+00:00") == "stale"


def test_fresh_vdo_metrics_replace_mobile_path_fields_only() -> None:
    probe = {
        "source": "streamml_http_probe",
        "upload_mbps": 20.0,
        "download_mbps": 80.0,
        "latency_ms": 5.0,
        "jitter_ms": 1.0,
        "packet_loss_percent": 0.0,
        "connection_capacity_mbps": 20.0,
    }
    phone = {
        "observed_at": "2026-07-17T12:00:00+00:00",
        "status": "connected",
        "metrics": {
            "available_outgoing_bitrate_kbps": 1800.0,
            "round_trip_time_ms": 160.0,
            "jitter_ms": 22.0,
            "packet_loss_percent": 4.0,
        },
    }
    merged = merge_vdo_network(probe, phone, "2026-07-17T12:00:01+00:00")
    assert merged == {
        "source": "vdo_ninja_webrtc_hybrid",
        "upload_mbps": 1.8,
        "download_mbps": 80.0,
        "latency_ms": 160.0,
        "jitter_ms": 22.0,
        "packet_loss_percent": 4.0,
        "connection_capacity_mbps": 1.8,
    }


def test_zero_vdo_bitrate_does_not_impersonate_the_mobile_connection() -> None:
    probe = {
        "source": "streamml_http_probe",
        "upload_mbps": 12.0,
        "download_mbps": 50.0,
        "latency_ms": 25.0,
        "jitter_ms": 2.0,
        "packet_loss_percent": 0.0,
        "connection_capacity_mbps": 12.0,
    }
    phone = {
        "observed_at": "2026-07-17T12:00:00+00:00",
        "status": "connected",
        "metrics": {"bitrate_kbps": 0.0},
    }

    merged = merge_vdo_network(probe, phone, "2026-07-17T12:00:01+00:00")
    assert merged == {
        "source": "vdo_ninja_webrtc_partial",
        "download_mbps": 50.0,
        "latency_ms": 25.0,
        "jitter_ms": 2.0,
        "packet_loss_percent": 0.0,
    }


def test_stale_phone_does_not_fall_back_to_the_server_network() -> None:
    phone = {
        "observed_at": "2026-07-17T12:00:00+00:00",
        "status": "connected",
        "metrics": {"bitrate_kbps": 2_000.0},
    }
    assert (
        merge_vdo_network(
            {"source": "streamml_http_probe", "upload_mbps": 100.0},
            phone,
            "2026-07-17T12:00:11+00:00",
        )
        is None
    )
