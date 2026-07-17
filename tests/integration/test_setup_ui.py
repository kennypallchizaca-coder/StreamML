from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.connector.streamml_connector.local_config import LocalConfigurationStore
from apps.connector.streamml_connector.setup_ui import (
    SetupService,
    SetupValidationError,
    normalize_connector_values,
    normalize_deployment_values,
)


class FakeVault:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def has(self, name: str) -> bool:
        return name in self.values

    def set(self, name: str, value: str) -> None:
        self.values[name] = value


def test_local_setup_keeps_sensitive_connector_values_out_of_json(tmp_path: Path):
    store = LocalConfigurationStore(tmp_path / "setup.json")
    vault = FakeVault()
    service = SetupService(store=store, vault=vault)  # type: ignore[arg-type]

    result = service.save_connector({
        "api_base_url": "http://127.0.0.1:8000",
        "obs_host": "127.0.0.1",
        "obs_port": 4455,
        "connector_name": "OBS de pruebas",
        "live_scene": "StreamML Live",
        "backup_scene": "StreamML Backup",
        "obs_password": "contraseña-que-no-debe-escribirse",
    })

    saved = store.path.read_text(encoding="utf-8")
    assert "contraseña-que-no-debe-escribirse" not in saved
    assert vault.values["obs_websocket_password"] == "contraseña-que-no-debe-escribirse"
    assert result["state"]["secrets"]["obs_websocket_password"] is True
    assert "obs_password" not in result["state"]["connector"]


def test_connector_gui_rejects_remote_obs_and_accepts_loopback_only():
    with pytest.raises(SetupValidationError, match="loopback"):
        normalize_connector_values({"api_base_url": "https://streamml.example", "obs_host": "192.168.1.25"})

    value = normalize_connector_values({
        "api_base_url": "https://streamml.example",
        "obs_host": "localhost",
        "obs_port": "4455",
        "connector_name": "OBS seguro",
        "live_scene": "Vivo",
        "backup_scene": "Respaldo",
    })
    assert value["api_base_url"] == "https://streamml.example"
    assert value["obs_host"] == "localhost"


def test_connection_check_uses_visible_unsaved_values(monkeypatch, tmp_path: Path):
    store = LocalConfigurationStore(tmp_path / "setup.json")
    store.save_connector(normalize_connector_values({
        "api_base_url": "http://127.0.0.1:8999",
        "obs_host": "127.0.0.1",
        "connector_name": "Configuración anterior",
    }))
    vault = FakeVault()
    service = SetupService(store=store, vault=vault)  # type: ignore[arg-type]
    observed: dict[str, object] = {}

    def fake_get(url: str, **_kwargs):
        observed["url"] = url
        return SimpleNamespace(is_success=True, status_code=200)

    class FakeObsClient:
        def __init__(self, config):
            observed["config"] = config

        def connect(self, password: str):
            observed["password"] = password

        def validate_scenes(self):
            return []

        def disconnect(self):
            return None

    monkeypatch.setattr("apps.connector.streamml_connector.setup_ui.httpx.get", fake_get)
    monkeypatch.setattr("apps.connector.streamml_connector.setup_ui.ObsClient", FakeObsClient)
    monkeypatch.setattr("apps.connector.streamml_connector.setup_ui.TokenStore.load", lambda _self: None)

    result = service.connector_checks({
        "api_base_url": "http://127.0.0.1:8000",
        "obs_host": "localhost",
        "obs_port": 4456,
        "connector_name": "Valores visibles",
        "live_scene": "Vivo",
        "backup_scene": "Respaldo",
        "obs_password": "clave-visible-no-guardada",
        "pairing_code": "CODIGO1",
    })

    assert observed["url"] == "http://127.0.0.1:8000/health"
    assert observed["password"] == "clave-visible-no-guardada"
    assert getattr(observed["config"], "obs_port") == 4456
    assert {item["status"] for item in result["checks"]} == {"ok"}


def test_deployment_validation_requires_https_and_keeps_password_in_vault(tmp_path: Path):
    certificate = tmp_path / "fullchain.pem"
    private_key = tmp_path / "privkey.pem"
    certificate.write_text("certificate", encoding="utf-8")
    private_key.write_text("private-key", encoding="utf-8")
    values = normalize_deployment_values({
        "public_origin": "https://streamml.example.com",
        "bootstrap_email": "admin@example.com",
        "tls_cert_file": str(certificate),
        "tls_key_file": str(private_key),
    })
    assert values["allowed_origins"] == "https://streamml.example.com"

    with pytest.raises(SetupValidationError, match="HTTPS"):
        normalize_deployment_values({
            "public_origin": "http://streamml.example.com",
            "bootstrap_email": "admin@example.com",
            "tls_cert_file": str(certificate),
            "tls_key_file": str(private_key),
        })

    store = LocalConfigurationStore(tmp_path / "setup.json")
    vault = FakeVault()
    service = SetupService(store=store, vault=vault)  # type: ignore[arg-type]
    result = service.save_deployment({
        **values,
        "bootstrap_password": "UnaClaveDePruebaSegura123",
    })
    saved = store.path.read_text(encoding="utf-8")
    assert "UnaClaveDePruebaSegura123" not in saved
    assert vault.has("deployment_bootstrap_password")
    assert result["state"]["secrets"]["deployment_token_secret"] is True
