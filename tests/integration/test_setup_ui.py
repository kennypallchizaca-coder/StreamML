from __future__ import annotations

from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import httpx
import pytest

from apps.connector.streamml_connector.local_config import LocalConfigurationStore
from apps.connector.streamml_connector.setup_ui import (
    SetupService,
    SetupHttpServer,
    SetupValidationError,
    normalize_connector_values,
    normalize_deployment_values,
)
from apps.connector.streamml_connector import setup_ui


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

    result = service.save_connector(
        {
            "api_base_url": "http://127.0.0.1:8000",
            "obs_host": "127.0.0.1",
            "obs_port": 4455,
            "connector_name": "OBS de pruebas",
            "live_scene": "StreamML Live",
            "backup_scene": "StreamML Backup",
            "obs_password": "contraseña-que-no-debe-escribirse",
        }
    )

    saved = store.path.read_text(encoding="utf-8")
    assert "contraseña-que-no-debe-escribirse" not in saved
    assert vault.values["obs_websocket_password"] == "contraseña-que-no-debe-escribirse"
    assert result["state"]["secrets"]["obs_websocket_password"] is True
    assert "obs_password" not in result["state"]["connector"]


def test_connector_gui_rejects_remote_obs_and_accepts_loopback_only():
    with pytest.raises(SetupValidationError, match="loopback"):
        normalize_connector_values({"api_base_url": "https://streamml.example", "obs_host": "192.168.1.25"})

    value = normalize_connector_values(
        {
            "api_base_url": "https://streamml.example",
            "obs_host": "localhost",
            "obs_port": "4455",
            "connector_name": "OBS seguro",
            "live_scene": "Vivo",
            "backup_scene": "Respaldo",
        }
    )
    assert value["api_base_url"] == "https://streamml.example"
    assert value["obs_host"] == "localhost"


def test_connection_check_uses_visible_unsaved_values(monkeypatch, tmp_path: Path):
    store = LocalConfigurationStore(tmp_path / "setup.json")
    store.save_connector(
        normalize_connector_values(
            {
                "api_base_url": "http://127.0.0.1:8999",
                "obs_host": "127.0.0.1",
                "connector_name": "Configuración anterior",
            }
        )
    )
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

    result = service.connector_checks(
        {
            "api_base_url": "http://127.0.0.1:8000",
            "obs_host": "localhost",
            "obs_port": 4456,
            "connector_name": "Valores visibles",
            "live_scene": "Vivo",
            "backup_scene": "Respaldo",
            "obs_password": "clave-visible-no-guardada",
            "pairing_code": "CODIGO1",
        }
    )

    assert observed["url"] == "http://127.0.0.1:8000/health"
    assert observed["password"] == "clave-visible-no-guardada"
    assert getattr(observed["config"], "obs_port") == 4456
    assert {item["status"] for item in result["checks"]} == {"ok"}


def test_deployment_validation_requires_https_and_keeps_password_in_vault(monkeypatch, tmp_path: Path):
    certificate = tmp_path / "fullchain.pem"
    private_key = tmp_path / "privkey.pem"
    certificate.write_text("certificate", encoding="utf-8")
    private_key.write_text("private-key", encoding="utf-8")

    class FakeTlsContext:
        def load_cert_chain(self, _certificate, _private_key):
            return None

    monkeypatch.setattr(setup_ui.ssl, "SSLContext", lambda _protocol: FakeTlsContext())
    values = normalize_deployment_values(
        {
            "public_origin": "https://streamml.example.com",
            "bootstrap_email": "admin@example.com",
            "tls_cert_file": str(certificate),
            "tls_key_file": str(private_key),
        }
    )
    assert values["allowed_origins"] == "https://streamml.example.com"

    with pytest.raises(SetupValidationError, match="HTTPS"):
        normalize_deployment_values(
            {
                "public_origin": "http://streamml.example.com",
                "bootstrap_email": "admin@example.com",
                "tls_cert_file": str(certificate),
                "tls_key_file": str(private_key),
            }
        )

    store = LocalConfigurationStore(tmp_path / "setup.json")
    vault = FakeVault()
    service = SetupService(store=store, vault=vault)  # type: ignore[arg-type]
    result = service.save_deployment(
        {
            **values,
            "bootstrap_password": "UnaClaveDePruebaSegura123",
        }
    )
    saved = store.path.read_text(encoding="utf-8")
    assert "UnaClaveDePruebaSegura123" not in saved
    assert vault.has("deployment_bootstrap_password")
    assert result["state"]["secrets"]["deployment_token_secret"] is True


def test_deployment_validation_rejects_invalid_tls_files(tmp_path: Path):
    certificate = tmp_path / "fullchain.pem"
    private_key = tmp_path / "privkey.pem"
    certificate.write_text("not-a-certificate", encoding="utf-8")
    private_key.write_text("not-a-private-key", encoding="utf-8")

    with pytest.raises(SetupValidationError, match="no son válidos"):
        normalize_deployment_values(
            {
                "public_origin": "https://streamml.example.com",
                "bootstrap_email": "admin@example.com",
                "tls_cert_file": str(certificate),
                "tls_key_file": str(private_key),
            }
        )


def test_new_pairing_restarts_a_running_connector(monkeypatch, tmp_path: Path):
    store = LocalConfigurationStore(tmp_path / "setup.json")
    vault = FakeVault()
    service = SetupService(store=store, vault=vault)  # type: ignore[arg-type]

    class RunningProcess:
        pid = 4321

        def poll(self):
            return None

    class FakeApiClient:
        def __init__(self, _config):
            pass

        def link(self, _code):
            return object()

        def close(self):
            pass

    calls: list[str] = []
    service._connector_process = RunningProcess()  # type: ignore[assignment]
    monkeypatch.setattr(setup_ui, "StreamMLApiClient", FakeApiClient)
    monkeypatch.setattr(setup_ui.TokenStore, "save", lambda _self, _credentials: None)
    monkeypatch.setattr(service, "stop_connector", lambda: calls.append("stop") or {})
    monkeypatch.setattr(service, "start_connector", lambda: calls.append("start") or {})

    result = service.save_connector(
        {
            "api_base_url": "http://127.0.0.1:8000",
            "obs_host": "127.0.0.1",
            "connector_name": "OBS de pruebas",
            "pairing_code": "CODIGO1234",
        }
    )

    assert calls == ["stop", "start"]
    assert result["restarted"] is True


def test_connector_start_uses_source_path_and_reports_running_state(monkeypatch, tmp_path: Path):
    store = LocalConfigurationStore(tmp_path / "setup.json")
    store.save_connector(
        normalize_connector_values(
            {
                "api_base_url": "http://127.0.0.1:8000",
                "obs_host": "127.0.0.1",
                "obs_port": 4855,
                "connector_name": "OBS de pruebas",
            }
        )
    )
    vault = FakeVault()
    vault.set("obs_websocket_password", "segura")
    service = SetupService(store=store, vault=vault)  # type: ignore[arg-type]
    observed: dict[str, object] = {}

    class RunningProcess:
        pid = 4321

        def poll(self):
            return None

    def fake_popen(command, **options):
        observed["command"] = command
        observed["options"] = options
        return RunningProcess()

    monkeypatch.setattr(setup_ui.TokenStore, "load", lambda _self: object())
    monkeypatch.setattr(setup_ui.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(setup_ui.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(setup_ui, "SETUP_LOG", tmp_path / "connector.log")

    result = service.start_connector()

    assert result["pid"] == 4321
    assert result["state"]["capabilities"]["connector_running"] is True
    assert observed["command"][-2:] == ["-m", "streamml_connector"]
    source = str(setup_ui.REPOSITORY_ROOT / "apps" / "connector")
    assert str(observed["options"]["env"]["PYTHONPATH"]).split(setup_ui.os.pathsep)[0] == source


def test_connector_start_never_reports_false_success(monkeypatch, tmp_path: Path):
    store = LocalConfigurationStore(tmp_path / "setup.json")
    store.save_connector(
        normalize_connector_values(
            {
                "api_base_url": "http://127.0.0.1:8000",
                "obs_host": "127.0.0.1",
                "connector_name": "OBS de pruebas",
            }
        )
    )
    vault = FakeVault()
    vault.set("obs_websocket_password", "segura")
    service = SetupService(store=store, vault=vault)  # type: ignore[arg-type]

    class StoppedProcess:
        pid = 4321

        def poll(self):
            return 1

    monkeypatch.setattr(setup_ui.TokenStore, "load", lambda _self: object())
    monkeypatch.setattr(setup_ui.subprocess, "Popen", lambda *_args, **_kwargs: StoppedProcess())
    monkeypatch.setattr(setup_ui.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(setup_ui, "SETUP_LOG", tmp_path / "connector.log")

    with pytest.raises(SetupValidationError, match="no pudo iniciar"):
        service.start_connector()
    assert service.state()["capabilities"]["connector_running"] is False


def test_setup_page_accepts_theme_query_and_renders_light_mode(tmp_path: Path):
    service = SetupService(
        store=LocalConfigurationStore(tmp_path / "setup.json"),
        vault=FakeVault(),  # type: ignore[arg-type]
    )
    server = SetupHttpServer(("127.0.0.1", 0), service)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        port = int(server.server_address[1])
        response = httpx.get(f"http://127.0.0.1:{port}/?theme=light", timeout=5)
        assert response.status_code == 200
        assert '<html lang="es" data-theme="light">' in response.text
        assert "style-src 'self'" in response.headers["content-security-policy"]
        assert "unsafe-inline" not in response.headers["content-security-policy"]
        assert 'id="theme-toggle"' in response.text
        assert 'href="/theme.css"' in response.text
        assert 'href="/setup.css"' in response.text
        assert 'href="/favicon.webp?v=2"' in response.text
        assert '<img src="/favicon.webp?v=2" alt="Nexa">' in response.text

        shared_theme = httpx.get(f"http://127.0.0.1:{port}/theme.css", timeout=5)
        local_styles = httpx.get(f"http://127.0.0.1:{port}/setup.css", timeout=5)
        favicon = httpx.get(f"http://127.0.0.1:{port}/favicon.webp", timeout=5)
        assert shared_theme.status_code == 200
        assert local_styles.status_code == 200
        assert favicon.status_code == 200
        assert favicon.headers["content-type"] == "image/webp"
        assert favicon.content == setup_ui.NEXA_FAVICON_FILE.read_bytes()
        assert "--sidebar-primary:" in shared_theme.text
        assert "var(--sidebar-accent)" in local_styles.text
        assert "oklch(" not in local_styles.text
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
