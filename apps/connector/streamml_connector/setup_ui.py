"""Loopback-only GUI for installing and configuring the StreamML local pieces.

This process is intentionally separate from the online API.  It is the only
component allowed to read OBS credentials or invoke Docker on the OBS machine.
Secrets are accepted over an authenticated loopback request and immediately
written to the operating-system credential vault; they are never returned by
the API or written to JSON files.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from http.cookies import SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse
import webbrowser

import httpx

from .api_client import ApiClientError, StreamMLApiClient
from .config import ConfigurationError, ConnectorConfig, _validate_api_url, _validate_obs_host
from .local_config import LocalConfigurationError, LocalConfigurationStore
from .obs_client import ObsClient
from .secrets import LocalSecretVault, SecretStorageError, TokenStore


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = REPOSITORY_ROOT / "infrastructure" / "docker" / "docker-compose.yml"
SETUP_LOG = LocalConfigurationStore().path.parent / "connector.log"
MAX_REQUEST_BYTES = 64 * 1024


class SetupValidationError(ValueError):
    """A friendly, non-sensitive validation message for the setup GUI."""


@dataclass(frozen=True, slots=True)
class CheckResult:
    id: str
    label: str
    status: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "status": self.status, "message": self.message}


def _as_text(values: dict[str, Any], key: str, default: str = "") -> str:
    value = values.get(key, default)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SetupValidationError(f"El campo {key} debe ser texto.")
    return value.strip()


def _as_int(values: dict[str, Any], key: str, default: int, *, minimum: int, maximum: int) -> int:
    value = values.get(key, default)
    if isinstance(value, bool):
        raise SetupValidationError(f"El campo {key} debe ser un número.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise SetupValidationError(f"El campo {key} debe ser un número entero.") from exc
    if not minimum <= number <= maximum:
        raise SetupValidationError(f"El campo {key} debe estar entre {minimum} y {maximum}.")
    return number


def _as_float(values: dict[str, Any], key: str, default: float, *, minimum: float, maximum: float) -> float:
    value = values.get(key, default)
    if isinstance(value, bool):
        raise SetupValidationError(f"El campo {key} debe ser un número.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SetupValidationError(f"El campo {key} debe ser un número.") from exc
    if not minimum <= number <= maximum:
        raise SetupValidationError(f"El campo {key} debe estar entre {minimum} y {maximum}.")
    return number


def _valid_uuid_or_empty(value: str) -> str | None:
    if not value:
        return None
    import uuid

    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise SetupValidationError("El identificador de transmisión debe ser un UUID válido.") from exc


def normalize_connector_values(values: dict[str, Any]) -> dict[str, Any]:
    """Validate the safe subset that may be stored in the local JSON file."""

    api_base_url = _as_text(values, "api_base_url", "http://127.0.0.1:8000")
    try:
        api_base_url = _validate_api_url(api_base_url)
        obs_host = _validate_obs_host(_as_text(values, "obs_host", "127.0.0.1"))
    except ConfigurationError as exc:
        raise SetupValidationError(str(exc)) from exc
    connector_name = _as_text(values, "connector_name", os.getenv("COMPUTERNAME") or "StreamML OBS")
    if not 1 <= len(connector_name) <= 100:
        raise SetupValidationError("El nombre del conector debe tener entre 1 y 100 caracteres.")
    live_scene = _as_text(values, "live_scene", "StreamML Live")
    backup_scene = _as_text(values, "backup_scene", "StreamML Backup")
    if not live_scene or not backup_scene or len(live_scene) > 120 or len(backup_scene) > 120:
        raise SetupValidationError("Los nombres de escena deben tener entre 1 y 120 caracteres.")
    return {
        "api_base_url": api_base_url,
        "obs_host": obs_host,
        "obs_port": _as_int(values, "obs_port", 4455, minimum=1, maximum=65535),
        "connector_name": connector_name,
        "session_id": _valid_uuid_or_empty(_as_text(values, "session_id")),
        "poll_interval_seconds": _as_float(values, "poll_interval_seconds", 1, minimum=0.2, maximum=60),
        "request_timeout_seconds": _as_float(values, "request_timeout_seconds", 10, minimum=1, maximum=60),
        "live_scene": live_scene,
        "backup_scene": backup_scene,
        "network_probe_interval_seconds": _as_float(values, "network_probe_interval_seconds", 5, minimum=1, maximum=60),
        "network_probe_bytes": _as_int(values, "network_probe_bytes", 262144, minimum=1024, maximum=524288),
    }


def connector_config_from_values(values: dict[str, Any]) -> ConnectorConfig:
    """Build the exact connector configuration shown in the GUI, ignoring env overrides."""

    normalized = normalize_connector_values(values)
    return ConnectorConfig(
        **normalized,
        reconnect_initial_seconds=1.0,
        reconnect_max_seconds=30.0,
        keyring_service=os.getenv("STREAMML_KEYRING_SERVICE", "streamml-connector"),
        log_level=os.getenv("STREAMML_LOG_LEVEL", "INFO").upper(),
    )


def _origin(value: str, *, name: str) -> tuple[str, str]:
    try:
        parsed = urlparse(value)
    except ValueError as exc:
        raise SetupValidationError(f"{name} no es una URL válida.") from exc
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SetupValidationError(f"{name} debe usar HTTPS, incluir un host y no contener credenciales ni parámetros.")
    if parsed.path not in {"", "/"}:
        raise SetupValidationError(f"{name} no debe incluir una ruta.")
    return parsed.geturl().rstrip("/"), parsed.hostname


def normalize_deployment_values(values: dict[str, Any]) -> dict[str, Any]:
    public_origin, public_host = _origin(_as_text(values, "public_origin"), name="La URL pública")
    raw_origins = _as_text(values, "allowed_origins", public_origin)
    origins = [item.strip().rstrip("/") for item in raw_origins.split(",") if item.strip()]
    if not origins or "*" in origins:
        raise SetupValidationError("Debes indicar una lista explícita de orígenes permitidos, sin comodines.")
    for item in origins:
        _origin(item, name="Cada origen permitido")
    media_base = _as_text(values, "mediamtx_public_base", f"{public_origin}/media").rstrip("/")
    parsed_media = urlparse(media_base)
    if parsed_media.scheme != "https" or not parsed_media.hostname:
        raise SetupValidationError("La URL pública de MediaMTX debe usar HTTPS.")
    email = _as_text(values, "bootstrap_email").lower()
    if "@" not in email or len(email) > 254:
        raise SetupValidationError("Ingresa un correo de administrador válido.")
    cert_file = _as_text(values, "tls_cert_file")
    key_file = _as_text(values, "tls_key_file")
    if not cert_file or not key_file:
        raise SetupValidationError("Indica las rutas del certificado TLS y de su clave privada.")
    if not Path(cert_file).is_file() or not Path(key_file).is_file():
        raise SetupValidationError("No se encontró el certificado TLS o su clave privada en las rutas indicadas.")
    rtmp_port_bind = _as_text(values, "rtmp_port_bind", "127.0.0.1:1935")
    webrtc_udp_port_bind = _as_text(values, "webrtc_udp_port_bind", "0.0.0.0:8189")
    if ":" not in rtmp_port_bind or ":" not in webrtc_udp_port_bind:
        raise SetupValidationError("Los puertos deben tener formato host:puerto.")
    return {
        "public_origin": public_origin,
        "allowed_origins": ",".join(origins),
        "mediamtx_public_base": media_base,
        "mediamtx_rtmp_publish_base": _as_text(values, "mediamtx_rtmp_publish_base"),
        "bootstrap_email": email,
        "mediamtx_image": _as_text(values, "mediamtx_image", "bluenviron/mediamtx:1.19.2"),
        "mediamtx_webrtc_additional_hosts": _as_text(values, "mediamtx_webrtc_additional_hosts", public_host),
        "rtmp_port_bind": rtmp_port_bind,
        "webrtc_udp_port_bind": webrtc_udp_port_bind,
        "tls_cert_file": str(Path(cert_file).resolve()),
        "tls_key_file": str(Path(key_file).resolve()),
    }


def _secret_presence(vault: LocalSecretVault) -> dict[str, bool]:
    return {name: vault.has(name) for name in (
        "obs_websocket_password",
        "deployment_token_secret",
        "deployment_media_auth_secret",
        "deployment_bootstrap_password",
        "deployment_restream_config_json",
    )}


def _safe_command_output(result: subprocess.CompletedProcess[str]) -> str:
    # Docker normally does not print values from the env file, but redact just
    # in case an underlying error echoed a line that looks like a credential.
    import re

    output = (result.stdout or "")[-3000:]
    return re.sub(r"(?i)(password|secret|token|key)\s*[=:]\s*[^\s]+", r"\1=[OCULTO]", output)


class SetupService:
    """Business operations behind the loopback GUI; easy to test without HTTP."""

    def __init__(self, *, store: LocalConfigurationStore | None = None, vault: LocalSecretVault | None = None) -> None:
        self.store = store or LocalConfigurationStore()
        self.vault = vault or LocalSecretVault()
        self._connector_process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    def state(self) -> dict[str, Any]:
        connector = {
            "api_base_url": "http://127.0.0.1:8000",
            "obs_host": "127.0.0.1",
            "obs_port": 4455,
            "connector_name": os.getenv("COMPUTERNAME") or "StreamML OBS",
            "session_id": "",
            "poll_interval_seconds": 1,
            "request_timeout_seconds": 10,
            "live_scene": "StreamML Live",
            "backup_scene": "StreamML Backup",
            "network_probe_interval_seconds": 5,
            "network_probe_bytes": 262144,
        }
        connector.update(self.store.connector())
        deployment = {
            "public_origin": "",
            "allowed_origins": "",
            "mediamtx_public_base": "",
            "mediamtx_rtmp_publish_base": "",
            "bootstrap_email": "",
            "mediamtx_image": "bluenviron/mediamtx:1.19.2",
            "mediamtx_webrtc_additional_hosts": "",
            "rtmp_port_bind": "127.0.0.1:1935",
            "webrtc_udp_port_bind": "0.0.0.0:8189",
            "tls_cert_file": "",
            "tls_key_file": "",
        }
        deployment.update(self.store.deployment())
        process_running = self._connector_process is not None and self._connector_process.poll() is None
        return {
            "connector": connector,
            "deployment": deployment,
            "secrets": _secret_presence(self.vault),
            "capabilities": {
                "docker_available": shutil.which("docker") is not None,
                "compose_file_available": COMPOSE_FILE.is_file(),
                "connector_running": process_running,
                "log_file": str(SETUP_LOG),
            },
        }

    def backup(self) -> dict[str, Any]:
        """Return a portable support backup that intentionally excludes every secret."""

        return {
            "format": "streamml-local-configuration-v1",
            "connector": self.store.connector(),
            "deployment": self.store.deployment(),
            "secrets_included": False,
            "message": "Las contraseñas, tokens, claves RTMP y certificados privados no se incluyen.",
        }

    def save_connector(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = normalize_connector_values(payload)
        config = connector_config_from_values(values)
        password = _as_text(payload, "obs_password")
        pairing_code = _as_text(payload, "pairing_code")
        linked = False
        if pairing_code:
            client = StreamMLApiClient(config)
            try:
                credentials = client.link(pairing_code)
                TokenStore(config.keyring_service, config.api_base_url, config.connector_name).save(credentials)
            finally:
                client.close()
            linked = True
        if password:
            self.vault.set("obs_websocket_password", password)
        self.store.save_connector(values)
        return {"message": "La configuración local se guardó de forma segura.", "linked": linked, "state": self.state()}

    def connector_checks(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            visible = payload or self.state()["connector"]
            config = connector_config_from_values(visible)
        except (ConfigurationError, SetupValidationError) as exc:
            return {"checks": [CheckResult("settings", "Configuración", "error", str(exc)).to_dict()]}
        checks: list[CheckResult] = []
        try:
            response = httpx.get(f"{config.api_base_url}/health", timeout=5, follow_redirects=False)
            checks.append(CheckResult("api", "API StreamML", "ok" if response.is_success else "error", "Disponible." if response.is_success else f"Respondió HTTP {response.status_code}."))
        except httpx.HTTPError:
            checks.append(CheckResult("api", "API StreamML", "error", "No se pudo conectar. Comprueba la URL y que el servidor esté iniciado."))
        try:
            pairing_code = _as_text(visible, "pairing_code")
            credentials = TokenStore(config.keyring_service, config.api_base_url, config.connector_name).load()
            pairing_ready = bool(credentials or pairing_code)
            message = "Conector vinculado." if credentials else ("Código listo para vincular al guardar." if pairing_code else "Falta el código de vínculo temporal.")
            checks.append(CheckResult("pairing", "Vinculación", "ok" if pairing_ready else "warning", message))
        except SecretStorageError:
            checks.append(CheckResult("pairing", "Vinculación", "error", "No se puede acceder al Administrador de credenciales de Windows."))
        try:
            password = _as_text(visible, "obs_password") or self.vault.get("obs_websocket_password")
            if not password:
                raise SecretStorageError("missing")
            obs = ObsClient(config)
            try:
                obs.connect(password)
                missing_scenes = obs.validate_scenes()
            finally:
                obs.disconnect()
            if missing_scenes:
                checks.append(CheckResult("obs", "OBS WebSocket", "error", "Conectado, pero faltan estas escenas: " + ", ".join(missing_scenes)))
            else:
                checks.append(CheckResult("obs", "OBS WebSocket", "ok", "Conectado; escenas en vivo y respaldo disponibles."))
        except SecretStorageError:
            checks.append(CheckResult("obs", "OBS WebSocket", "warning", "Guarda la contraseña de OBS para poder comprobarlo."))
        except Exception:
            checks.append(CheckResult("obs", "OBS WebSocket", "error", "No se pudo conectar. Abre OBS, activa WebSocket y revisa host, puerto y contraseña."))
        return {"checks": [item.to_dict() for item in checks]}

    def start_connector(self) -> dict[str, Any]:
        config = connector_config_from_values(self.store.connector())
        if not self.vault.has("obs_websocket_password"):
            raise SetupValidationError("Guarda primero la contraseña de OBS en el asistente local.")
        stored = TokenStore(config.keyring_service, config.api_base_url, config.connector_name).load()
        if stored is None:
            raise SetupValidationError("Vincula primero el conector con un código temporal de la aplicación.")
        with self._lock:
            if self._connector_process is not None and self._connector_process.poll() is None:
                return {"message": "El conector ya está en ejecución.", "pid": self._connector_process.pid}
            SETUP_LOG.parent.mkdir(parents=True, exist_ok=True)
            log_handle = SETUP_LOG.open("a", encoding="utf-8")
            connector_environment = os.environ.copy()
            for name in (
                "STREAMML_API_URL", "OBS_WEBSOCKET_HOST", "OBS_WEBSOCKET_PORT",
                "STREAMML_CONNECTOR_NAME", "STREAMML_SESSION_ID", "STREAMML_POLL_INTERVAL_SECONDS",
                "STREAMML_REQUEST_TIMEOUT_SECONDS", "STREAMML_LIVE_SCENE", "STREAMML_BACKUP_SCENE",
                "STREAMML_NETWORK_PROBE_INTERVAL_SECONDS", "STREAMML_NETWORK_PROBE_BYTES",
            ):
                connector_environment.pop(name, None)
            options: dict[str, Any] = {"cwd": str(REPOSITORY_ROOT), "stdout": log_handle, "stderr": subprocess.STDOUT, "close_fds": True, "env": connector_environment}
            if os.name == "nt":
                options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                self._connector_process = subprocess.Popen(
                    [sys.executable, "-m", "streamml_connector"], **options
                )
            finally:
                log_handle.close()
        return {"message": "Conector iniciado. Puedes ver su estado desde la transmisión en unos segundos.", "pid": self._connector_process.pid}

    def stop_connector(self) -> dict[str, Any]:
        with self._lock:
            process = self._connector_process
            if process is None or process.poll() is not None:
                return {"message": "El conector no está en ejecución."}
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            self._connector_process = None
        return {"message": "Monitorización detenida correctamente."}

    def save_deployment(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = normalize_deployment_values(payload)
        bootstrap_password = _as_text(payload, "bootstrap_password")
        restream_config = _as_text(payload, "restream_config_json")
        if bootstrap_password:
            if len(bootstrap_password) < 12:
                raise SetupValidationError("La contraseña del administrador debe tener al menos 12 caracteres.")
            self.vault.set("deployment_bootstrap_password", bootstrap_password)
        elif not self.vault.has("deployment_bootstrap_password"):
            raise SetupValidationError("Define una contraseña para la cuenta administradora.")
        if restream_config:
            try:
                parsed = json.loads(restream_config)
            except json.JSONDecodeError as exc:
                raise SetupValidationError("La configuración de retransmisión debe ser JSON válido.") from exc
            if not isinstance(parsed, dict):
                raise SetupValidationError("La configuración de retransmisión debe ser un objeto JSON.")
            self.vault.set("deployment_restream_config_json", json.dumps(parsed, separators=(",", ":")))
        for name in ("deployment_token_secret", "deployment_media_auth_secret"):
            provided = _as_text(payload, name)
            if provided:
                if len(provided) < 32:
                    raise SetupValidationError("Los secretos del servidor deben tener al menos 32 caracteres.")
                self.vault.set(name, provided)
            elif not self.vault.has(name):
                # Generated values are intentionally never returned to the browser.
                self.vault.set(name, secrets.token_urlsafe(48))
        self.store.save_deployment(values)
        return {"message": "La configuración del servidor se guardó. Los secretos quedaron cifrados en el almacén del sistema.", "state": self.state()}

    def _deployment_env(self) -> dict[str, str]:
        values = normalize_deployment_values(self.store.deployment())
        secrets_by_name = {
            "STREAMML_TOKEN_SECRET": self.vault.get("deployment_token_secret"),
            "STREAMML_MEDIA_AUTH_SECRET": self.vault.get("deployment_media_auth_secret"),
            "STREAMML_BOOTSTRAP_PASSWORD": self.vault.get("deployment_bootstrap_password"),
            "STREAMML_RESTREAM_CONFIG_JSON": self.vault.get("deployment_restream_config_json") or "{}",
        }
        if any(not value for value in secrets_by_name.values() if value != "{}"):
            raise SetupValidationError("Faltan secretos del servidor. Guarda la configuración del servidor nuevamente.")
        return {
            **{key: str(value) for key, value in secrets_by_name.items()},
            "STREAMML_ALLOWED_ORIGINS": str(values["allowed_origins"]),
            "STREAMML_MEDIAMTX_PUBLIC_BASE": str(values["mediamtx_public_base"]),
            "STREAMML_MEDIAMTX_RTMP_PUBLISH_BASE": str(values["mediamtx_rtmp_publish_base"]),
            "STREAMML_BOOTSTRAP_EMAIL": str(values["bootstrap_email"]),
            "MEDIAMTX_IMAGE": str(values["mediamtx_image"]),
            "MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS": str(values["mediamtx_webrtc_additional_hosts"]),
            "MEDIAMTX_RTMP_PORT_BIND": str(values["rtmp_port_bind"]),
            "MEDIAMTX_WEBRTC_UDP_PORT_BIND": str(values["webrtc_udp_port_bind"]),
            "TLS_CERT_FILE": str(values["tls_cert_file"]),
            "TLS_KEY_FILE": str(values["tls_key_file"]),
        }

    def _with_temporary_env(self, action: Callable[[Path], subprocess.CompletedProcess[str]]) -> subprocess.CompletedProcess[str]:
        if shutil.which("docker") is None:
            raise SetupValidationError("Docker Desktop no está instalado o no está iniciado.")
        if not COMPOSE_FILE.is_file():
            raise SetupValidationError("No se encontró el archivo Docker Compose de StreamML.")
        environment = self._deployment_env()
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False) as stream:
                temporary_path = Path(stream.name)
                for key, value in environment.items():
                    stream.write(f"{key}={value}\n")
            temporary_path.chmod(0o600)
            return action(temporary_path)
        finally:
            if temporary_path and temporary_path.exists():
                try:
                    # Best effort only: Windows/Docker administrators can still
                    # inspect a running container, so this is not a substitute
                    # for host access controls.
                    temporary_path.write_bytes(b"\0" * temporary_path.stat().st_size)
                    temporary_path.unlink()
                except OSError:
                    pass

    def deployment_check(self) -> dict[str, Any]:
        command_result = self._with_temporary_env(lambda path: subprocess.run(
            ["docker", "compose", "--env-file", str(path), "-f", str(COMPOSE_FILE), "config", "-q"],
            cwd=REPOSITORY_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False,
        ))
        if command_result.returncode != 0:
            raise SetupValidationError("Docker Compose no pudo validar la configuración: " + _safe_command_output(command_result))
        return {"message": "Docker Compose validó la infraestructura. Los secretos no se escribieron de forma permanente.", "checks": [CheckResult("compose", "Infraestructura", "ok", "Configuración válida.").to_dict()]}

    def start_deployment(self) -> dict[str, Any]:
        command_result = self._with_temporary_env(lambda path: subprocess.run(
            ["docker", "compose", "--env-file", str(path), "-f", str(COMPOSE_FILE), "up", "-d", "--build"],
            cwd=REPOSITORY_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300, check=False,
        ))
        if command_result.returncode != 0:
            raise SetupValidationError("Docker Compose no pudo iniciar los servicios: " + _safe_command_output(command_result))
        return {"message": "Infraestructura iniciada o actualizada. Comprueba la URL pública después de que terminen los contenedores.", "output": _safe_command_output(command_result)}


class SetupHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], service: SetupService) -> None:
        self.service = service
        self.access_token = secrets.token_urlsafe(32)
        self.csp_nonce = secrets.token_urlsafe(16)
        super().__init__(address, SetupRequestHandler)


class SetupRequestHandler(BaseHTTPRequestHandler):
    server: SetupHttpServer

    def log_message(self, _format: str, *_args: object) -> None:
        # Requests can include a pairing code in their body. Do not log them.
        return

    def do_GET(self) -> None:  # noqa: N802
        if not self._allowed_host():
            self._json_error(HTTPStatus.FORBIDDEN, "Este asistente solo acepta conexiones locales.")
            return
        if self.path == "/":
            self._html_page()
        elif self.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
        elif self.path == "/api/state":
            if not self._authorized():
                return
            self._json(HTTPStatus.OK, self.server.service.state())
        elif self.path == "/api/backup":
            if not self._authorized():
                return
            self._json(HTTPStatus.OK, self.server.service.backup())
        else:
            self._json_error(HTTPStatus.NOT_FOUND, "Ruta no encontrada.")

    def do_POST(self) -> None:  # noqa: N802
        if not self._allowed_host() or not self._authorized():
            return
        if self.headers.get("content-type", "").split(";", 1)[0] != "application/json":
            self._json_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Se esperaba JSON.")
            return
        try:
            length = int(self.headers.get("content-length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= MAX_REQUEST_BYTES:
            self._json_error(HTTPStatus.BAD_REQUEST, "El tamaño de la solicitud no es válido.")
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json_error(HTTPStatus.BAD_REQUEST, "El JSON no es válido.")
            return
        if not isinstance(payload, dict):
            self._json_error(HTTPStatus.BAD_REQUEST, "La solicitud debe ser un objeto JSON.")
            return
        actions: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "/api/connector/save": lambda body: self.server.service.save_connector(body),
            "/api/connector/check": lambda body: self.server.service.connector_checks(body),
            "/api/connector/start": lambda _body: self.server.service.start_connector(),
            "/api/connector/stop": lambda _body: self.server.service.stop_connector(),
            "/api/deployment/save": lambda body: self.server.service.save_deployment(body),
            "/api/deployment/check": lambda _body: self.server.service.deployment_check(),
            "/api/deployment/start": lambda _body: self.server.service.start_deployment(),
        }
        action = actions.get(self.path)
        if action is None:
            self._json_error(HTTPStatus.NOT_FOUND, "Ruta no encontrada.")
            return
        try:
            self._json(HTTPStatus.OK, action(payload))
        except (SetupValidationError, ConfigurationError, LocalConfigurationError, SecretStorageError, ApiClientError) as exc:
            self._json_error(HTTPStatus.BAD_REQUEST, str(exc))
        except subprocess.TimeoutExpired:
            self._json_error(HTTPStatus.GATEWAY_TIMEOUT, "La operación tardó demasiado. Revisa Docker Desktop y vuelve a intentarlo.")
        except Exception:
            self._json_error(HTTPStatus.INTERNAL_SERVER_ERROR, "La operación no se pudo completar. Revisa el registro local y vuelve a intentarlo.")

    def _allowed_host(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0].casefold()
        return host in {"127.0.0.1", "localhost", "[::1]", "::1"}

    def _authorized(self) -> bool:
        header_token = self.headers.get("X-StreamML-Setup-Token")
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        cookie_token = cookie.get("streamml_setup")
        if header_token != self.server.access_token and (
            cookie_token is None or cookie_token.value != self.server.access_token
        ):
            self._json_error(HTTPStatus.FORBIDDEN, "Sesión local no autorizada. Cierra y vuelve a abrir el asistente.")
            return False
        return True

    def _headers(self, content_type: str, length: int) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", f"default-src 'self'; style-src 'unsafe-inline'; script-src 'self' 'nonce-{self.server.csp_nonce}'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._headers("application/json; charset=utf-8", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _json_error(self, status: HTTPStatus, message: str) -> None:
        self._json(status, {"message": message})

    def _html_page(self) -> None:
        page = _PAGE.replace("<script>", f'<script nonce="{self.server.csp_nonce}">')
        page = page.replace(
            "location.hash.slice(1)",
            f"location.hash.slice(1) || {json.dumps(self.server.access_token)}",
        )
        data = page.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self._headers("text/html; charset=utf-8", len(data))
        # Strict + HttpOnly lets the StreamML web application link to the
        # assistant without exposing its local session to another website.
        self.send_header(
            "Set-Cookie",
            f"streamml_setup={self.server.access_token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=7200",
        )
        self.end_headers()
        self.wfile.write(data)


_PAGE = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Asistente local · StreamML</title><style>
:root{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif;background:#0b1020;color:#eef2ff}*{box-sizing:border-box}body{margin:0}.wrap{max-width:1050px;margin:auto;padding:30px 20px 70px}h1{margin:0;font-size:clamp(1.65rem,4vw,2.4rem)}h2{margin:0 0 8px;font-size:1.2rem}p{line-height:1.5;color:#b9c3dc}.lead{max-width:800px}.card{background:#141b31;border:1px solid #293454;border-radius:16px;padding:22px;margin-top:20px;box-shadow:0 12px 30px #0002}.grid{display:grid;gap:15px;grid-template-columns:repeat(2,minmax(0,1fr))}.span{grid-column:1/-1}label{display:grid;gap:6px;font-size:.9rem;color:#dce4fa}input,textarea{width:100%;background:#0d1428;border:1px solid #3d4b71;border-radius:9px;padding:10px;color:#fff;font:inherit}textarea{min-height:86px;resize:vertical}input:focus,textarea:focus{outline:2px solid #7c9cff;border-color:transparent}button{border:0;border-radius:9px;padding:10px 14px;background:#7895ff;color:#071023;font:600 .92rem inherit;cursor:pointer}button.secondary{background:#253252;color:#e5ecff}button:disabled{opacity:.55;cursor:wait}.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.status{display:grid;gap:8px;margin:15px 0}.notice{padding:12px 14px;border-radius:9px;background:#172342;border:1px solid #3a4d7e}.notice.error{background:#3a1c2a;border-color:#a84c6c}.notice.ok{background:#17352e;border-color:#397d67}.check{padding:10px;border-left:4px solid #d6a23b;background:#10182b}.check.ok{border-color:#4fb58b}.check.error{border-color:#dc5a73}.muted{font-size:.86rem;color:#a9b5d1}.secret{color:#9ee6c7;font-weight:600}.tabs{display:flex;gap:7px;margin-top:22px}.tabs button{background:#202b48;color:#dce4fa}.tabs button.active{background:#7895ff;color:#071023}.panel{display:none}.panel.active{display:block}@media(max-width:680px){.grid{grid-template-columns:1fr}.span{grid-column:auto}.wrap{padding:24px 14px}}
</style></head><body><main class="wrap"><h1>Asistente local de StreamML</h1><p class="lead">Configura este equipo sin editar archivos ni copiar contraseñas a la terminal. Las claves se guardan en el Administrador de credenciales del sistema; la interfaz solo muestra si existen.</p><div id="notice" class="notice">Cargando configuración local…</div><div class="tabs"><button class="active" data-tab="connector">1. OBS y conector</button><button data-tab="server">2. Servidor Docker</button><button data-tab="help">Ayuda</button></div>
<section id="connector" class="panel active card"><h2>OBS y monitorización</h2><p>Usa la misma computadora donde está OBS. Genera el código temporal en la aplicación web, en <strong>Configuración → Conexiones</strong>, y pégalo aquí una sola vez.</p><form id="connector-form"><div class="grid"><label>URL de la API<input name="api_base_url" required inputmode="url"></label><label>Nombre de este conector<input name="connector_name" required maxlength="100"></label><label>Host de OBS<input name="obs_host" required></label><label>Puerto de OBS WebSocket<input name="obs_port" required type="number" min="1" max="65535"></label><label>Escena en vivo<input name="live_scene" required maxlength="120"></label><label>Escena de respaldo<input name="backup_scene" required maxlength="120"></label><label>Intervalo de telemetría (s)<input name="poll_interval_seconds" type="number" min="0.2" max="60" step="0.1"></label><label>Tiempo máximo de API (s)<input name="request_timeout_seconds" type="number" min="1" max="60" step="1"></label><label>Intervalo de prueba de red (s)<input name="network_probe_interval_seconds" type="number" min="1" max="60"></label><label>Tamaño de prueba de red (bytes)<input name="network_probe_bytes" type="number" min="1024" max="524288" step="1024"></label><label class="span">Contraseña de OBS <span class="secret" id="obs-secret"></span><input name="obs_password" type="password" autocomplete="new-password" placeholder="Déjala vacía para conservar la guardada"></label><label class="span">Código temporal de vínculo <input name="pairing_code" autocomplete="one-time-code" placeholder="No se guarda; úsalo solo al vincular"></label></div><div class="row"><button type="submit">Guardar y vincular</button><button class="secondary" type="button" id="connector-check">Comprobar conexión</button><button class="secondary" type="button" id="connector-start">Iniciar monitorización</button><button class="secondary" type="button" id="connector-stop">Detener monitorización</button></div></form><div id="connector-checks" class="status"></div></section>
<section id="server" class="panel card"><h2>Servidor de producción con Docker</h2><p>Esta sección prepara e inicia la infraestructura protegida. Requiere Docker Desktop, un dominio HTTPS y un certificado TLS ya emitido. Para desarrollo local usa la URL de API del primer paso; no abras el servidor de desarrollo a Internet.</p><form id="server-form"><div class="grid"><label>URL pública HTTPS<input name="public_origin" required placeholder="https://streamml.midominio.com"></label><label>Orígenes permitidos (separados por coma)<input name="allowed_origins" placeholder="https://streamml.midominio.com"></label><label>Correo administrador<input name="bootstrap_email" required type="email"></label><label>Contraseña administrador <span class="secret" id="bootstrap-secret"></span><input name="bootstrap_password" type="password" autocomplete="new-password" placeholder="Déjala vacía para conservar la guardada"></label><label>URL pública de MediaMTX<input name="mediamtx_public_base" placeholder="https://streamml.midominio.com/media"></label><label>RTMP público (opcional)<input name="mediamtx_rtmp_publish_base" placeholder="rtmps://streamml.midominio.com:1935"></label><label>Ruta de certificado TLS<input name="tls_cert_file" required placeholder="C:\certs\fullchain.pem"></label><label>Ruta de clave TLS<input name="tls_key_file" required placeholder="C:\certs\privkey.pem"></label><label>Host WebRTC MediaMTX<input name="mediamtx_webrtc_additional_hosts"></label><label>Imagen MediaMTX<input name="mediamtx_image"></label><label>Enlace RTMP de Docker<input name="rtmp_port_bind"></label><label>Enlace UDP WebRTC<input name="webrtc_udp_port_bind"></label><label class="span">Destinos de retransmisión JSON (opcional, contiene claves de plataforma) <span class="secret" id="restream-secret"></span><textarea name="restream_config_json" placeholder='{"stream-id":{"youtube":"rtmps://.../CLAVE"}}'></textarea></label><label>Secreto de tokens de servidor (opcional; se genera y cifra si queda vacío) <span class="secret" id="token-secret"></span><input name="deployment_token_secret" type="password" autocomplete="new-password"></label><label>Secreto de MediaMTX (opcional; se genera y cifra si queda vacío) <span class="secret" id="media-secret"></span><input name="deployment_media_auth_secret" type="password" autocomplete="new-password"></label></div><div class="row"><button type="submit">Guardar servidor</button><button class="secondary" type="button" id="server-check">Validar Docker Compose</button><button class="secondary" type="button" id="server-start">Iniciar o actualizar servicios</button></div></form><div id="server-checks" class="status"></div></section>
<section id="help" class="panel card"><h2>Uso seguro</h2><p><strong>1.</strong> Abre OBS, activa WebSocket y crea las escenas indicadas. <strong>2.</strong> Guarda aquí la URL de API y la contraseña de OBS. <strong>3.</strong> Crea una transmisión en StreamML, genera el código temporal y pégalo para vincular. <strong>4.</strong> Pulsa “Comprobar conexión” y luego “Iniciar monitorización”.</p><p>Las contraseñas, tokens, claves RTMP y secretos se guardan en el Administrador de credenciales de Windows y nunca se devuelven a la página. Los ajustes no sensibles están en la carpeta de datos de StreamML para que el conector pueda reiniciarse. Para renovar una credencial, escribe el nuevo valor y guarda: el anterior se reemplaza sin mostrarse.</p><p>Si falla OBS, revisa que WebSocket esté activo, que el host sea 127.0.0.1 y que el puerto/contraseña coincidan. Si falla Docker, inicia Docker Desktop, verifica el certificado y vuelve a pulsar “Validar Docker Compose”. El registro sin secretos del conector se guarda localmente.</p><div class="row"><button class="secondary" type="button" id="backup-download">Descargar copia de configuración (sin secretos)</button></div></section></main><script>
const notice=document.querySelector('#notice'), token=location.hash.slice(1);let state={};
function say(text,type=''){notice.textContent=text;notice.className='notice '+type}
function formData(id){const data={};new FormData(document.querySelector(id)).forEach((v,k)=>data[k]=v);return data}
function fill(id,values){const form=document.querySelector(id);Object.entries(values||{}).forEach(([k,v])=>{const input=form.elements.namedItem(k);if(input&&typeof v!=='object')input.value=String(v??'')})}
function secret(id,present){document.querySelector(id).textContent=present?'Guardada de forma segura.':''}
function renderChecks(id,checks=[]){const root=document.querySelector(id);root.replaceChildren(...checks.map(c=>{const el=document.createElement('div');el.className='check '+c.status;el.textContent=`${c.label}: ${c.message}`;return el}))}
function apply(next){state=next;fill('#connector-form',state.connector);fill('#server-form',state.deployment);const s=state.secrets||{};secret('#obs-secret',s.obs_websocket_password);secret('#bootstrap-secret',s.deployment_bootstrap_password);secret('#restream-secret',s.deployment_restream_config_json);secret('#token-secret',s.deployment_token_secret);secret('#media-secret',s.deployment_media_auth_secret)}
async function call(path,body={}){if(!token)throw Error('Sesión local inválida. Cierra y vuelve a abrir el asistente.');const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-StreamML-Setup-Token':token},body:JSON.stringify(body)});const j=await r.json();if(!r.ok)throw Error(j.message||'No se pudo completar la operación.');return j}
async function load(){const r=await fetch('/api/state',{headers:{'X-StreamML-Setup-Token':token}});const j=await r.json();if(!r.ok)throw Error(j.message||'No se pudo cargar.');apply(j);say('Listo. Completa los pasos en orden.','ok')}
async function action(button,fn){button.disabled=true;try{const result=await fn();if(result.state)apply(result.state);if(result.checks)renderChecks(button.id.startsWith('server')?'#server-checks':'#connector-checks',result.checks);say(result.message||'Operación completada.','ok')}catch(e){say(e instanceof Error?e.message:'No se pudo completar la operación.','error')}finally{button.disabled=false}}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===b.dataset.tab))});
document.querySelector('#connector-form').onsubmit=e=>{e.preventDefault();const b=e.submitter;action(b,()=>call('/api/connector/save',formData('#connector-form')))};
document.querySelector('#server-form').onsubmit=e=>{e.preventDefault();const b=e.submitter;action(b,()=>call('/api/deployment/save',formData('#server-form')))};
document.querySelector('#connector-check').onclick=e=>action(e.currentTarget,()=>call('/api/connector/check',formData('#connector-form')));
document.querySelector('#connector-start').onclick=e=>action(e.currentTarget,()=>call('/api/connector/start'));
document.querySelector('#connector-stop').onclick=e=>action(e.currentTarget,()=>call('/api/connector/stop'));
document.querySelector('#server-check').onclick=e=>action(e.currentTarget,()=>call('/api/deployment/check'));
document.querySelector('#server-start').onclick=e=>action(e.currentTarget,()=>call('/api/deployment/start'));
document.querySelector('#backup-download').onclick=async e=>{const b=e.currentTarget;b.disabled=true;try{const r=await fetch('/api/backup',{headers:{'X-StreamML-Setup-Token':token}});const j=await r.json();if(!r.ok)throw Error(j.message||'No se pudo crear la copia.');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(j,null,2)],{type:'application/json'}));a.download='streamml-config-backup.json';a.click();URL.revokeObjectURL(a.href);say('Copia sin secretos descargada.','ok')}catch(err){say(err instanceof Error?err.message:'No se pudo crear la copia.','error')}finally{b.disabled=false}};
load().catch(e=>say(e instanceof Error?e.message:'No se pudo cargar la configuración.','error'));
</script></body></html>"""


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("el puerto debe ser un número entero") from exc
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("el puerto debe estar entre 1024 y 65535")
    return port


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="streamml-setup", description="Open the local StreamML setup GUI.")
    parser.add_argument("--port", type=_port, default=8765, metavar="PUERTO")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    args = parser.parse_args(argv)
    try:
        server = SetupHttpServer(("127.0.0.1", args.port), SetupService())
    except OSError as exc:
        print(f"No se pudo iniciar el asistente local en el puerto {args.port}: {exc}", file=sys.stderr)
        return 2
    url = f"http://127.0.0.1:{args.port}/#{server.access_token}"
    print(f"Asistente local de StreamML disponible en http://127.0.0.1:{args.port}/")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(cli())
