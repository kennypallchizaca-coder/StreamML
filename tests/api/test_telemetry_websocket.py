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
