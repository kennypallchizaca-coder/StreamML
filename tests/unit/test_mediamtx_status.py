from src.streamml.services.mediamtx_status import MediaMtxStatusClient, media_path_state


def test_media_path_state_requires_an_explicit_server_signal() -> None:
    assert media_path_state({"ready": True}) == "connected"
    assert media_path_state({"available": True}) == "connected"
    assert media_path_state({"online": True}) == "connected"
    assert media_path_state({"ready": False, "available": False}) == "waiting"


def test_status_client_caches_a_verified_path() -> None:
    calls: list[str] = []

    def fetch_json(url: str, _timeout_seconds: float) -> dict:
        calls.append(url)
        return {"ready": True}

    client = MediaMtxStatusClient("http://mediamtx:9997", fetch_json=fetch_json)

    assert client.status_for_path("stream-abc") == "connected"
    assert client.status_for_path("stream-abc") == "connected"
    assert calls == ["http://mediamtx:9997/v3/paths/get/stream-abc"]


def test_status_client_without_private_api_remains_unverified() -> None:
    assert MediaMtxStatusClient("").status_for_path("stream-abc") == "unverified"
