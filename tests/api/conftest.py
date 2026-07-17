from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.config import Settings
from apps.api.main import create_app


ROOT = Path(__file__).resolve().parents[2]
TEST_PASSWORD = "Correct-Horse-StreamML-2026"


@pytest.fixture()
def app(tmp_path):
    settings = Settings(
        root_dir=ROOT,
        database_path=tmp_path / "streamml-test.sqlite3",
        allowed_origins=("https://testserver",),
        cookie_secure=False,
        enforce_https=False,
        token_secret="test-token-secret-" * 4,
        media_auth_secret="test-media-secret-" * 4,
        mediamtx_public_base="https://testserver",
        bootstrap_email="owner@example.com",
        bootstrap_password=TEST_PASSWORD,
    )
    return create_app(settings)


@pytest.fixture()
def client(app):
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def login(client: TestClient, email: str = "owner@example.com", password: str = TEST_PASSWORD):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response


def create_session(client: TestClient, name: str = "Transmisión de prueba") -> dict:
    response = client.post("/api/v1/sessions", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()

