"""Environment-backed connector configuration without secret values."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
import platform
from typing import Any
from urllib.parse import urlparse

from .local_config import LocalConfigurationError, LocalConfigurationStore


class ConfigurationError(ValueError):
    """Raised when connector configuration would weaken a security boundary."""


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be numeric.") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero.")
    return value


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer.") from exc
    if not 1 <= value <= 65535:
        raise ConfigurationError(f"{name} must be a valid TCP port.")
    return value


def _env_positive_int(name: str, default: int, *, maximum: int) -> int:
    raw = os.getenv(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer.") from exc
    if not 1 <= value <= maximum:
        raise ConfigurationError(f"{name} must be between 1 and {maximum}.")
    return value


def _saved_local_settings() -> dict[str, Any]:
    """Load GUI-managed non-secret values without weakening env overrides."""

    try:
        return LocalConfigurationStore().connector()
    except LocalConfigurationError as exc:
        raise ConfigurationError(str(exc)) from exc


def _value(name: str, saved: dict[str, Any], default: Any) -> Any:
    """Environment variables keep precedence for managed deployments/tests."""

    env_value = os.getenv(name)
    if env_value is not None:
        return env_value
    stored_name = {
        "STREAMML_API_URL": "api_base_url",
        "OBS_WEBSOCKET_HOST": "obs_host",
        "OBS_WEBSOCKET_PORT": "obs_port",
        "STREAMML_CONNECTOR_NAME": "connector_name",
        "STREAMML_SESSION_ID": "session_id",
        "STREAMML_POLL_INTERVAL_SECONDS": "poll_interval_seconds",
        "STREAMML_REQUEST_TIMEOUT_SECONDS": "request_timeout_seconds",
        "STREAMML_LIVE_SCENE": "live_scene",
        "STREAMML_BACKUP_SCENE": "backup_scene",
        "STREAMML_NETWORK_PROBE_INTERVAL_SECONDS": "network_probe_interval_seconds",
        "STREAMML_NETWORK_PROBE_BYTES": "network_probe_bytes",
    }.get(name)
    return saved.get(stored_name, default) if stored_name else default


def _stored_float(name: str, saved: dict[str, Any], default: float) -> float:
    raw = _value(name, saved, default)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be numeric.") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero.")
    return value


def _stored_int(name: str, saved: dict[str, Any], default: int) -> int:
    raw = _value(name, saved, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be an integer.") from exc
    if not 1 <= value <= 65535:
        raise ConfigurationError(f"{name} must be a valid TCP port.")
    return value


def _stored_positive_int(name: str, saved: dict[str, Any], default: int, *, maximum: int) -> int:
    raw = _value(name, saved, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be an integer.") from exc
    if not 1 <= value <= maximum:
        raise ConfigurationError(f"{name} must be between 1 and {maximum}.")
    return value


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _validate_api_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigurationError("STREAMML_API_URL must be an absolute HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationError("STREAMML_API_URL cannot contain credentials, query, or fragment.")
    if parsed.scheme != "https" and not _is_loopback(parsed.hostname):
        raise ConfigurationError("STREAMML_API_URL must use HTTPS outside localhost development.")
    return raw_url.rstrip("/")


def _validate_obs_host(host: str) -> str:
    if not _is_loopback(host):
        raise ConfigurationError(
            "OBS_WEBSOCKET_HOST must be localhost or an explicit loopback address; "
            "OBS WebSocket must never be exposed to the network."
        )
    return host


@dataclass(frozen=True, slots=True)
class ConnectorConfig:
    api_base_url: str
    obs_host: str
    obs_port: int
    connector_name: str
    session_id: str | None
    poll_interval_seconds: float
    request_timeout_seconds: float
    reconnect_initial_seconds: float
    reconnect_max_seconds: float
    keyring_service: str
    log_level: str
    live_scene: str = "StreamML Live"
    backup_scene: str = "StreamML Backup"
    network_probe_interval_seconds: float = 5.0
    network_probe_bytes: int = 256 * 1024


def load_config() -> ConnectorConfig:
    """Load non-secret configuration and enforce local OBS plus HTTPS boundaries."""

    saved = _saved_local_settings()
    api_base_url = _validate_api_url(str(_value("STREAMML_API_URL", saved, "http://127.0.0.1:8000")))
    reconnect_initial = _env_float("STREAMML_RECONNECT_INITIAL_SECONDS", 1.0)
    reconnect_max = _env_float("STREAMML_RECONNECT_MAX_SECONDS", 30.0)
    if reconnect_max < reconnect_initial:
        raise ConfigurationError("STREAMML_RECONNECT_MAX_SECONDS cannot be lower than the initial delay.")

    connector_name = str(_value("STREAMML_CONNECTOR_NAME", saved, platform.node())).strip()
    if not connector_name or len(connector_name) > 100:
        raise ConfigurationError("STREAMML_CONNECTOR_NAME must contain 1 to 100 characters.")

    session_id = _value("STREAMML_SESSION_ID", saved, None)
    if session_id is not None:
        session_id = str(session_id).strip() or None

    log_level = os.getenv("STREAMML_LOG_LEVEL", "INFO").upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigurationError("STREAMML_LOG_LEVEL is invalid.")

    return ConnectorConfig(
        api_base_url=api_base_url,
        obs_host=_validate_obs_host(str(_value("OBS_WEBSOCKET_HOST", saved, "127.0.0.1"))),
        obs_port=_stored_int("OBS_WEBSOCKET_PORT", saved, 4455),
        connector_name=connector_name,
        session_id=session_id,
        poll_interval_seconds=_stored_float("STREAMML_POLL_INTERVAL_SECONDS", saved, 1.0),
        request_timeout_seconds=_stored_float("STREAMML_REQUEST_TIMEOUT_SECONDS", saved, 10.0),
        reconnect_initial_seconds=reconnect_initial,
        reconnect_max_seconds=reconnect_max,
        keyring_service=os.getenv("STREAMML_KEYRING_SERVICE", "streamml-connector"),
        log_level=log_level,
        live_scene=str(_value("STREAMML_LIVE_SCENE", saved, "StreamML Live")).strip() or "StreamML Live",
        backup_scene=str(_value("STREAMML_BACKUP_SCENE", saved, "StreamML Backup")).strip() or "StreamML Backup",
        network_probe_interval_seconds=_stored_float("STREAMML_NETWORK_PROBE_INTERVAL_SECONDS", saved, 5.0),
        network_probe_bytes=_stored_positive_int("STREAMML_NETWORK_PROBE_BYTES", saved, 256 * 1024, maximum=512 * 1024),
    )
