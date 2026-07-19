"""Non-secret local configuration for the StreamML desktop assistant.

Passwords, API tokens and stream keys do not belong here.  They are stored by
``LocalSecretVault`` in the operating-system credential vault.  Keeping this
file deliberately boring makes it safe to inspect while troubleshooting.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


class LocalConfigurationError(ValueError):
    """Raised when the assistant's non-secret configuration is malformed."""


_CONNECTOR_KEYS = {
    "api_base_url",
    "obs_host",
    "obs_port",
    "connector_name",
    "session_id",
    "poll_interval_seconds",
    "request_timeout_seconds",
    "live_scene",
    "backup_scene",
    "network_probe_interval_seconds",
    "network_probe_bytes",
}

_DEPLOYMENT_KEYS = {
    "public_origin",
    "allowed_origins",
    "mediamtx_public_base",
    "mediamtx_rtmp_publish_base",
    "bootstrap_email",
    "mediamtx_image",
    "mediamtx_webrtc_additional_hosts",
    "rtmp_port_bind",
    "webrtc_udp_port_bind",
    "tls_cert_file",
    "tls_key_file",
}


def app_data_dir() -> Path:
    """Return the per-user StreamML data directory without using a secret path."""

    raw = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
    base = Path(raw) if raw else Path.home() / ".local" / "share"
    return base / "StreamML"


class LocalConfigurationStore:
    """Read and atomically persist only non-sensitive desktop settings."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_data_dir() / "setup.json"

    def load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {"connector": {}, "deployment": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise LocalConfigurationError(
                "La configuración local no se puede leer. Restáurala desde una copia o elimínala."
            ) from exc
        if not isinstance(value, dict):
            raise LocalConfigurationError("La configuración local tiene un formato no válido.")
        connector = value.get("connector", {})
        deployment = value.get("deployment", {})
        if not isinstance(connector, dict) or not isinstance(deployment, dict):
            raise LocalConfigurationError("La configuración local tiene secciones no válidas.")
        return {
            "connector": {key: connector[key] for key in _CONNECTOR_KEYS if key in connector},
            "deployment": {key: deployment[key] for key in _DEPLOYMENT_KEYS if key in deployment},
        }

    def connector(self) -> dict[str, Any]:
        return self.load()["connector"]

    def deployment(self) -> dict[str, Any]:
        return self.load()["deployment"]

    def save_connector(self, values: dict[str, Any]) -> None:
        self._save_section("connector", values, _CONNECTOR_KEYS)

    def save_deployment(self, values: dict[str, Any]) -> None:
        self._save_section("deployment", values, _DEPLOYMENT_KEYS)

    def _save_section(self, name: str, values: dict[str, Any], allowed: set[str]) -> None:
        if not isinstance(values, dict):
            raise LocalConfigurationError("Los ajustes deben ser un objeto.")
        current = self.load()
        current[name] = {key: values[key] for key in allowed if key in values}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(current)

    def _atomic_write(self, value: dict[str, dict[str, Any]]) -> None:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".streamml-", suffix=".json", dir=str(self.path.parent))
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.chmod(temporary_path, 0o600)
            except OSError:
                # Windows ACLs are inherited from LOCALAPPDATA.  The file has no
                # secrets even when the platform does not support POSIX modes.
                pass
            os.replace(temporary_path, self.path)
        except OSError as exc:
            raise LocalConfigurationError("No se pudo guardar la configuración local.") from exc
        finally:
            if temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
