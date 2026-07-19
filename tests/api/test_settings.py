from fastapi.testclient import TestClient

from conftest import TEST_PASSWORD, create_session, login


def test_settings_are_persisted_and_password_change_requires_current_password(client: TestClient):
    login(client)
    initial = client.get("/api/v1/settings")
    assert initial.status_code == 200
    assert initial.json()["stream"]["live_scene"] == "StreamML Live"

    preferences = {
        "language": "es",
        "timezone": "America/Guayaquil",
        "dark_mode": False,
        "alert_detail": "high",
    }
    assert client.put("/api/v1/settings/preferences", json=preferences).status_code == 200
    stream = {
        "preferred_resolution": "720p",
        "preferred_profile": "medium",
        "platform": "twitch",
        "live_scene": "Escena principal",
        "backup_scene": "Escena respaldo",
        "network_probe_interval_seconds": 9,
        "network_probe_bytes": 65536,
    }
    assert client.put("/api/v1/settings/stream", json=stream).status_code == 200
    assert (
        client.put(
            "/api/v1/settings/account",
            json={
                "display_name": "Alexis",
                "current_password": "incorrect-password",
                "new_password": "New-Secure-Password-2026",
            },
        ).status_code
        == 400
    )
    updated = client.put(
        "/api/v1/settings/account",
        json={
            "display_name": "Alexis",
            "current_password": TEST_PASSWORD,
            "new_password": "New-Secure-Password-2026",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["user"]["display_name"] == "Alexis"

    persisted = client.get("/api/v1/settings").json()
    assert persisted["preferences"] == preferences
    assert persisted["stream"] == stream
    client.post("/api/v1/auth/logout")
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "email": "owner@example.com",
                "password": "New-Secure-Password-2026",
            },
        ).status_code
        == 200
    )


def test_new_session_uses_configured_defaults_and_external_video_link_is_persisted(client: TestClient):
    login(client)
    assert (
        client.put(
            "/api/v1/settings/stream",
            json={
                "preferred_resolution": "720p",
                "preferred_profile": "medium",
                "platform": "kick",
                "live_scene": "StreamML Live",
                "backup_scene": "StreamML Backup",
                "network_probe_interval_seconds": 5,
                "network_probe_bytes": 262144,
            },
        ).status_code
        == 200
    )
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Evento IRL",
            "planned_duration_hours": "4",
            "connection_type": "mobile",
        },
    )
    assert created.status_code == 201
    session = created.json()
    assert session["configuration"] == {
        "platform": "kick",
        "resolution": "720p",
        "initial_profile": "medium",
        "planned_duration_hours": "4",
        "connection_type": "mobile",
    }

    invalid = client.put(
        f"/api/v1/settings/sessions/{session['id']}/video-link",
        json={"embed_url": "https://vdo.ninja/?push=phone-only"},
    )
    assert invalid.status_code == 422
    updated = client.put(
        f"/api/v1/settings/sessions/{session['id']}/video-link",
        json={"embed_url": "https://vdo.ninja/?view=external-camera&cleanoutput"},
    )
    assert updated.status_code == 200
    fetched = client.get(f"/api/v1/sessions/{session['id']}").json()
    assert fetched["vdo_ninja"]["embed_url"] == "https://vdo.ninja/?view=external-camera&cleanoutput"
    assert fetched["vdo_ninja"]["source"] == "external"


def test_connector_receives_saved_runtime_settings_and_history_delete_preserves_preferences(client: TestClient):
    login(client)
    session = create_session(client)
    stream = {
        "preferred_resolution": "480p",
        "preferred_profile": "low",
        "platform": "youtube",
        "live_scene": "Live personalizado",
        "backup_scene": "Respaldo personalizado",
        "network_probe_interval_seconds": 11,
        "network_probe_bytes": 32768,
    }
    assert client.put("/api/v1/settings/stream", json=stream).status_code == 200
    code = client.post("/api/v1/pairing/codes", json={"session_id": session["id"]}).json()["code"]
    linked = client.post(
        "/api/v1/connectors/link",
        json={
            "code": code,
            "connector_name": "OBS local",
            "connector_version": "1.0.0",
        },
    )
    assert linked.status_code == 200
    response = client.get(
        "/api/v1/connectors/settings",
        headers={"Authorization": f"Bearer {linked.json()['access_token']}"},
    )
    assert response.status_code == 200
    runtime = response.json()
    assert runtime.pop("vdo_bridge_url").startswith(f"https://testserver/vdo-bridge/{session['id']}?token=")
    assert runtime == {
        "live_scene": "Live personalizado",
        "backup_scene": "Respaldo personalizado",
        "network_probe_interval_seconds": 11,
        "network_probe_bytes": 32768,
    }
    deleted = client.request("DELETE", "/api/v1/settings/history", json={"confirmation": "DELETE_HISTORY"})
    assert deleted.status_code == 200
    assert deleted.json()["deleted_sessions"] == 1
    assert client.get("/api/v1/sessions").json()["items"] == []
    assert client.get("/api/v1/settings").json()["stream"] == stream
