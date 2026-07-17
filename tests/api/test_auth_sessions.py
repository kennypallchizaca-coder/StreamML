from fastapi.testclient import TestClient

from conftest import TEST_PASSWORD, create_session, login


def test_auth_session_creation_and_listing(client: TestClient):
    assert client.get("/health").json()["production_ready"] is False
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "incorrect"},
    ).status_code == 401

    login(client)
    created = create_session(client)
    assert created["vdo_ninja"]["phone_url"].startswith("https://vdo.ninja/")
    assert created["stream"]["webrtc_url"].startswith("https://testserver/")
    assert created["stream"]["whip_publish_url"].startswith("https://testserver/")
    fetched = client.get(f"/api/v1/sessions/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]
    listed = client.get("/api/v1/sessions")
    assert listed.status_code == 200
    payload = listed.json()
    rows = payload.get("items", payload.get("sessions", []))
    assert [item["id"] for item in rows] == [created["id"]]


def test_sessions_are_isolated_by_user(app):
    with TestClient(app, base_url="https://testserver") as owner:
        login(owner)
        session_id = create_session(owner)["id"]
        app.state.database.create_user_if_missing("other@example.com", TEST_PASSWORD)

    with TestClient(app, base_url="https://testserver") as other:
        login(other, "other@example.com")
        assert other.get(f"/api/v1/sessions/{session_id}").status_code == 404
        assert other.get(f"/api/v1/streams/{session_id}").status_code == 404


def test_pairing_code_is_temporary_and_one_use(client: TestClient):
    login(client)
    session_id = create_session(client)["id"]
    issued = client.post("/api/v1/pairing/codes", json={"session_id": session_id})
    assert issued.status_code == 201
    code = issued.json()["code"]
    link_payload = {"code": code, "connector_name": "OBS local", "connector_version": "0.1.0"}
    linked = client.post("/api/v1/connectors/link", json=link_payload)
    assert linked.status_code == 200
    assert linked.json()["session_id"] == session_id
    assert client.post("/api/v1/connectors/link", json=link_payload).status_code == 400
