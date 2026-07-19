from fastapi.testclient import TestClient
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from conftest import create_session, login


def _linked_connector(client: TestClient, session_id: str) -> str:
    code = client.post("/api/v1/pairing/codes", json={"session_id": session_id}).json()["code"]
    response = client.post(
        "/api/v1/connectors/link",
        json={"code": code, "connector_name": "OBS local", "connector_version": "0.1.0"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _telemetry(session_id: str, sequence: int = 1) -> dict:
    return {
        "session_id": session_id,
        "source": "obs_websocket_5",
        "observed_at": "2026-07-17T12:00:00Z",
        "sequence": sequence,
        "metrics": {
            "obs_connected": True,
            "stream_active": True,
            "stream_reconnecting": False,
            "active_fps": 59.94,
            "render_skipped_frames": 0,
            "render_total_frames": 600,
            "output_skipped_frames": 2,
            "output_total_frames": 600,
            "output_congestion": 0.01,
            "output_bytes": 1000000,
            "output_bitrate_kbps": 4200.0,
        },
        "unsupported": {
            "latency_ms": None,
            "packet_loss_percent": None,
            "upload_mbps": None,
            "download_mbps": None,
            "connection_capacity_mbps": None,
        },
    }


def _network() -> dict:
    return {
        "source": "streamml_http_probe",
        "upload_mbps": 1.0,
        "download_mbps": 8.0,
        "latency_ms": 80.0,
        "jitter_ms": 4.0,
        "packet_loss_percent": 0.0,
        "connection_capacity_mbps": 1.0,
    }


def _healthy_network() -> dict:
    return {
        "source": "streamml_http_probe",
        "upload_mbps": 20.0,
        "download_mbps": 80.0,
        "latency_ms": 20.0,
        "jitter_ms": 2.0,
        "packet_loss_percent": 0.0,
        "connection_capacity_mbps": 20.0,
    }


def _vdo_telemetry(session_id: str, sequence: int = 1, status: str = "connected") -> dict:
    return {
        "session_id": session_id,
        "source": "vdo_ninja_iframe",
        "reporter_id": "browser-test-reporter",
        "sequence": sequence,
        "observed_at": "2026-07-17T12:00:00Z",
        "status": status,
        "metrics": {
            "bitrate_kbps": 2100.0,
            "available_outgoing_bitrate_kbps": 2500.0,
            "packet_loss_percent": 2.5,
            "jitter_ms": 18.0,
            "round_trip_time_ms": 140.0,
            "frames_per_second": 29.97,
        }
        if status == "connected"
        else {},
    }


def test_telemetry_persists_broadcasts_and_is_idempotent(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    token = _linked_connector(client, session_id)
    headers = {"Authorization": f"Bearer {token}"}

    with client.websocket_connect(f"/ws/sessions/{session_id}", headers={"origin": "https://testserver"}) as websocket:
        assert websocket.receive_json()["type"] == "snapshot"
        accepted = client.post("/api/v1/telemetry", json=_telemetry(session_id), headers=headers)
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["inference"]["message"] == "Datos insuficientes para una predicción válida"
        assert websocket.receive_json()["type"] == "telemetry"

    duplicate = client.post("/api/v1/telemetry", json=_telemetry(session_id), headers=headers)
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True


def test_compatible_network_telemetry_runs_reactive_model_and_agent(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    token = _linked_connector(client, session_id)
    headers = {"Authorization": f"Bearer {token}"}
    payload = _telemetry(session_id)
    payload["network"] = _network()

    response = client.post("/api/v1/telemetry", json=payload, headers=headers)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["inference"]["status"] == "executed"
    reactive = next(item for item in result["inference"]["predictions"] if item["model_role"] == "reactive")
    assert reactive["status"] == "executed"
    assert reactive["recommendation"] == "low"
    assert result["agent_decision"]["action"] == "reduce"
    assert result["agent_decision"]["target_profile"] == "low"
    assert result["control_command"]["command_type"] == "set_profile"

    pending = client.get("/api/v1/connectors/commands/next", headers=headers)
    assert pending.status_code == 200
    command = pending.json()["command"]
    assert command["id"] == result["control_command"]["id"]
    assert command["payload"]["profile"] == "low"
    ack = client.post(
        f"/api/v1/connectors/commands/{command['id']}/ack",
        json={"success": True, "error_message": None},
        headers=headers,
    )
    assert ack.status_code == 200
    assert client.get("/api/v1/connectors/commands/next", headers=headers).json()["command"] is None

    detail = client.get(f"/api/v1/sessions/{session_id}").json()
    assert detail["status"] == "active"
    assert detail["telemetry"]["upload_mbps"] == 1.0
    assert detail["telemetry"]["current_profile"] == "low"
    assert detail["agent_decision"]["target_profile"] == "low"


def test_vdo_ninja_metrics_override_pc_path_for_models_and_dashboard(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    token = _linked_connector(client, session_id)

    observed_at = datetime.now(timezone.utc).isoformat()
    phone_payload = _vdo_telemetry(session_id)
    phone_payload["observed_at"] = observed_at
    phone = client.post("/api/v1/telemetry/vdo-ninja", json=phone_payload)
    assert phone.status_code == 200, phone.text
    assert phone.json()["phone_status"] == "connected"

    payload = _telemetry(session_id)
    payload["observed_at"] = observed_at
    payload["network"] = _network()
    response = client.post(
        "/api/v1/telemetry",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    detail = client.get(f"/api/v1/sessions/{session_id}").json()
    assert detail["telemetry"]["phone_status"] == "connected"
    assert detail["telemetry"]["phone_bitrate_kbps"] == 2100.0
    assert detail["telemetry"]["upload_mbps"] == 2.5
    assert detail["telemetry"]["connection_capacity_mbps"] == 2.5
    assert detail["telemetry"]["latency_ms"] == 140.0
    assert detail["telemetry"]["jitter_ms"] == 18.0
    assert detail["telemetry"]["packet_loss_percent"] == 2.5
    assert detail["telemetry"]["network_source"] == "vdo_ninja_webrtc_hybrid"


def test_connected_phone_without_mobile_capacity_blocks_inference(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    token = _linked_connector(client, session_id)
    phone = _vdo_telemetry(session_id)
    phone["metrics"] = {"frames_per_second": 30.0}
    assert client.post("/api/v1/telemetry/vdo-ninja", json=phone).status_code == 200

    payload = _telemetry(session_id)
    payload["network"] = _network()
    response = client.post(
        "/api/v1/telemetry",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["inference"]["status"] == "blocked"
    assert all(item["status"] == "blocked" for item in result["inference"]["predictions"])
    detail = client.get(f"/api/v1/sessions/{session_id}").json()
    assert detail["telemetry"]["upload_mbps"] is None
    assert detail["telemetry"]["connection_capacity_mbps"] is None


def test_stale_vdo_signal_activates_backup_and_stable_recovery_restores_live(
    client: TestClient,
):
    login(client)
    session_id = create_session(client)["id"]
    token = _linked_connector(client, session_id)
    headers = {"Authorization": f"Bearer {token}"}

    phone = _vdo_telemetry(session_id, sequence=1)
    phone["observed_at"] = "2026-07-17T12:00:00Z"
    assert client.post("/api/v1/telemetry/vdo-ninja", json=phone).status_code == 200

    first = _telemetry(session_id, sequence=1)
    first["network"] = _healthy_network()
    assert client.post("/api/v1/telemetry", json=first, headers=headers).status_code == 200
    initial_command = client.get("/api/v1/connectors/commands/next", headers=headers).json()["command"]
    if initial_command:
        assert (
            client.post(
                f"/api/v1/connectors/commands/{initial_command['id']}/ack",
                json={"success": True, "error_message": None},
                headers=headers,
            ).status_code
            == 200
        )

    stale = _telemetry(session_id, sequence=2)
    stale["observed_at"] = "2026-07-17T12:00:11Z"
    stale["network"] = _healthy_network()
    grace = client.post("/api/v1/telemetry", json=stale, headers=headers).json()
    assert grace["agent_decision"]["reason_code"] == "signal_loss_grace_period"
    assert grace["control_command"] is None

    lost = _telemetry(session_id, sequence=3)
    lost["observed_at"] = "2026-07-17T12:00:15Z"
    lost["network"] = _healthy_network()
    backup = client.post("/api/v1/telemetry", json=lost, headers=headers).json()
    assert backup["agent_decision"]["action"] == "switch_to_backup"
    assert backup["control_command"]["command_type"] == "activate_backup"

    command = client.get("/api/v1/connectors/commands/next", headers=headers).json()["command"]
    assert command["command_type"] == "activate_backup"
    assert (
        client.post(
            f"/api/v1/connectors/commands/{command['id']}/ack",
            json={"success": True, "error_message": None},
            headers=headers,
        ).status_code
        == 200
    )

    recovered_phone = _vdo_telemetry(session_id, sequence=2)
    recovered_phone["observed_at"] = "2026-07-17T12:00:16Z"
    assert client.post("/api/v1/telemetry/vdo-ninja", json=recovered_phone).status_code == 200
    recovering = _telemetry(session_id, sequence=4)
    recovering["observed_at"] = "2026-07-17T12:00:16Z"
    recovering["network"] = _healthy_network()
    result = client.post("/api/v1/telemetry", json=recovering, headers=headers).json()
    assert result["agent_decision"]["action"] == "maintain_backup"

    fresh_phone = _vdo_telemetry(session_id, sequence=3)
    fresh_phone["observed_at"] = "2026-07-17T12:00:26Z"
    assert client.post("/api/v1/telemetry/vdo-ninja", json=fresh_phone).status_code == 200
    restored = _telemetry(session_id, sequence=5)
    restored["observed_at"] = "2026-07-17T12:00:27Z"
    restored["network"] = _healthy_network()
    restore = client.post("/api/v1/telemetry", json=restored, headers=headers).json()
    assert restore["agent_decision"]["action"] == "restore_live"
    assert restore["control_command"]["command_type"] == "restore_live"


def test_vdo_event_keeps_current_agent_profile_in_live_snapshot(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    token = _linked_connector(client, session_id)
    headers = {"Authorization": f"Bearer {token}"}
    telemetry = _telemetry(session_id)
    telemetry["network"] = _network()
    assert client.post("/api/v1/telemetry", json=telemetry, headers=headers).status_code == 200

    with client.websocket_connect(f"/ws/sessions/{session_id}", headers={"origin": "https://testserver"}) as websocket:
        assert websocket.receive_json()["type"] == "snapshot"
        phone = _vdo_telemetry(session_id)
        reported = client.post("/api/v1/telemetry/vdo-ninja", json=phone)
        assert reported.status_code == 200
        event = websocket.receive_json()
        assert event["type"] == "vdo_telemetry"
        assert event["telemetry"]["current_profile"] == "low"


def test_vdo_ninja_endpoint_is_tenant_scoped_and_validated(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    payload = _vdo_telemetry(session_id)
    payload["metrics"]["packet_loss_percent"] = 101
    assert client.post("/api/v1/telemetry/vdo-ninja", json=payload).status_code == 422

    client.post("/api/v1/auth/logout")
    assert client.post("/api/v1/telemetry/vdo-ninja", json=_vdo_telemetry(session_id)).status_code == 401


def test_vdo_metric_coalescing_never_reuses_an_old_capacity(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    first = _vdo_telemetry(session_id, sequence=1)
    first["observed_at"] = "2026-07-17T12:00:00Z"
    assert client.post("/api/v1/telemetry/vdo-ninja", json=first).status_code == 200
    later = _vdo_telemetry(session_id, sequence=2)
    later["observed_at"] = "2026-07-17T12:00:10Z"
    later["metrics"] = {"frames_per_second": 30.0}
    assert client.post("/api/v1/telemetry/vdo-ninja", json=later).status_code == 200

    latest = client.app.state.database.latest_vdo_telemetry(
        client.app.state.database.get_session_by_id(session_id)["user_id"], session_id
    )
    assert latest["metrics"] == {"frames_per_second": 30.0}


def test_obs_bridge_token_reports_without_a_user_cookie(client: TestClient):
    login(client)
    created = create_session(client)
    session_id = created["id"]
    bridge_url = created["vdo_ninja"]["bridge_url"]
    bridge_token = parse_qs(urlparse(bridge_url).query)["token"][0]
    client.post("/api/v1/auth/logout")

    headers = {"Authorization": f"Bearer {bridge_token}"}
    configuration = client.get(f"/api/v1/telemetry/vdo-ninja/{session_id}/bridge", headers=headers)
    assert configuration.status_code == 200, configuration.text
    assert "view=" in configuration.json()["embed_url"]
    reported = client.post(
        "/api/v1/telemetry/vdo-ninja",
        json=_vdo_telemetry(session_id),
        headers=headers,
    )
    assert reported.status_code == 200, reported.text


def test_connector_can_measure_authenticated_http_path(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    token = _linked_connector(client, session_id)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/network/probe/latency", headers=headers).status_code == 204
    download = client.get("/api/v1/network/probe/download", params={"size": 65536}, headers=headers)
    assert download.status_code == 200
    assert len(download.content) == 65536
    upload = client.post(
        "/api/v1/network/probe/upload",
        content=b"U" * 65536,
        headers={**headers, "Content-Type": "application/octet-stream"},
    )
    assert upload.status_code == 200
    assert upload.json()["received_bytes"] == 65536
    assert client.get("/api/v1/network/probe/latency").status_code == 401


def test_failed_obs_command_rolls_back_agent_state_for_retry(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    token = _linked_connector(client, session_id)
    headers = {"Authorization": f"Bearer {token}"}
    payload = _telemetry(session_id)
    payload["network"] = _network()

    first = client.post("/api/v1/telemetry", json=payload, headers=headers).json()
    command = first["control_command"]
    failed = client.post(
        f"/api/v1/connectors/commands/{command['id']}/ack",
        json={"success": False, "error_message": "ObsRejected"},
        headers=headers,
    )
    assert failed.status_code == 200

    payload["sequence"] = 2
    payload["observed_at"] = "2026-07-17T12:00:01Z"
    second = client.post("/api/v1/telemetry", json=payload, headers=headers).json()
    assert second["agent_decision"]["action"] == "reduce"
    assert second["control_command"]["id"] != command["id"]


def test_stale_control_command_expires_before_connector_delivery(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    token = _linked_connector(client, session_id)
    headers = {"Authorization": f"Bearer {token}"}
    session = client.app.state.database.get_session_by_id(session_id)
    command = client.app.state.database.enqueue_control_command(
        user_id=session["user_id"],
        session_id=session_id,
        connector_id=None,
        command_type="activate_backup",
        payload={"reason": "test", "previous_backup_active": False},
    )
    with client.app.state.database._connect() as connection:
        connection.execute(
            "UPDATE control_commands SET created_at=? WHERE id=?",
            ("2026-01-01T00:00:00+00:00", command["id"]),
        )

    pending = client.get("/api/v1/connectors/commands/next", headers=headers)
    assert pending.status_code == 200
    assert pending.json()["command"] is None
    with client.app.state.database._connect() as connection:
        stored = connection.execute(
            "SELECT status,error_message FROM control_commands WHERE id=?", (command["id"],)
        ).fetchone()
    assert stored["status"] == "failed"
    assert stored["error_message"] == "Command expired before delivery."
