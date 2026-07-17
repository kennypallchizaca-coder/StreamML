from fastapi.testclient import TestClient

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


def test_telemetry_persists_broadcasts_and_is_idempotent(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    token = _linked_connector(client, session_id)
    headers = {"Authorization": f"Bearer {token}"}

    with client.websocket_connect(
        f"/ws/sessions/{session_id}", headers={"origin": "https://testserver"}
    ) as websocket:
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
    reactive = next(
        item for item in result["inference"]["predictions"]
        if item["model_role"] == "reactive"
    )
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


def test_connector_can_measure_authenticated_http_path(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    token = _linked_connector(client, session_id)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/network/probe/latency", headers=headers).status_code == 204
    download = client.get(
        "/api/v1/network/probe/download", params={"size": 65536}, headers=headers
    )
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
