"""HTTPS client for connector linking and telemetry delivery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from . import __version__
from .config import ConnectorConfig
from .secrets import ConnectorCredentials


class ApiClientError(RuntimeError):
    """Sanitized API failure that never includes response bodies or secrets."""


@dataclass(frozen=True, slots=True)
class TelemetryReceipt:
    accepted: bool
    telemetry_id: str | None = None


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeSettings:
    live_scene: str
    backup_scene: str
    network_probe_interval_seconds: float
    network_probe_bytes: int


class StreamMLApiClient:
    def __init__(
        self,
        config: ConnectorConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.api_base_url,
            timeout=config.request_timeout_seconds,
            transport=transport,
            headers={"User-Agent": f"StreamML-Connector/{__version__}"},
            follow_redirects=False,
        )

    def link(self, code: str) -> ConnectorCredentials:
        response = self._request(
            "POST",
            "/api/v1/connectors/link",
            json={
                "code": code,
                "connector_name": self._config.connector_name,
                "connector_version": __version__,
            },
        )
        data = self._json_object(response)
        try:
            access_token = str(data["access_token"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiClientError("The pairing response did not contain a connector token.") from exc
        if not access_token:
            raise ApiClientError("The pairing response contained an empty connector token.")
        return ConnectorCredentials(
            access_token=access_token,
            connector_id=_optional_string(data.get("connector_id")),
            session_id=_optional_string(data.get("session_id")),
        )

    def send_telemetry(
        self, credentials: ConnectorCredentials, payload: dict[str, Any]
    ) -> TelemetryReceipt:
        response = self._request(
            "POST",
            "/api/v1/telemetry",
            headers={"Authorization": f"Bearer {credentials.access_token}"},
            json=payload,
        )
        data = self._json_object(response)
        return TelemetryReceipt(
            accepted=bool(data.get("accepted", True)),
            telemetry_id=_optional_string(data.get("telemetry_id") or data.get("id")),
        )

    def next_command(self, credentials: ConnectorCredentials) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            "/api/v1/connectors/commands/next",
            headers={"Authorization": f"Bearer {credentials.access_token}"},
        )
        command = self._json_object(response).get("command")
        if command is None:
            return None
        if not isinstance(command, dict) or not command.get("id"):
            raise ApiClientError("The command response was invalid.")
        return command

    def connector_settings(self, credentials: ConnectorCredentials) -> ConnectorRuntimeSettings:
        response = self._request(
            "GET", "/api/v1/connectors/settings",
            headers={"Authorization": f"Bearer {credentials.access_token}"},
        )
        data = self._json_object(response)
        try:
            live_scene = str(data["live_scene"]).strip()
            backup_scene = str(data["backup_scene"]).strip()
            interval = float(data["network_probe_interval_seconds"])
            probe_bytes = int(data["network_probe_bytes"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiClientError("The connector settings response was invalid.") from exc
        if not live_scene or not backup_scene or not 1 <= interval <= 60 or not 1024 <= probe_bytes <= 512 * 1024:
            raise ApiClientError("The connector settings response was outside safe limits.")
        return ConnectorRuntimeSettings(live_scene, backup_scene, interval, probe_bytes)

    def acknowledge_command(
        self,
        credentials: ConnectorCredentials,
        command_id: str,
        *,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        self._request(
            "POST",
            f"/api/v1/connectors/commands/{command_id}/ack",
            headers={"Authorization": f"Bearer {credentials.access_token}"},
            json={"success": success, "error_message": error_message},
        )

    def probe_latency(self, credentials: ConnectorCredentials) -> None:
        self._request(
            "GET", "/api/v1/network/probe/latency",
            headers={"Authorization": f"Bearer {credentials.access_token}"},
        )

    def probe_download(self, credentials: ConnectorCredentials, size: int) -> int:
        response = self._request(
            "GET", "/api/v1/network/probe/download",
            params={"size": size},
            headers={"Authorization": f"Bearer {credentials.access_token}"},
        )
        return len(response.content)

    def probe_upload(self, credentials: ConnectorCredentials, payload: bytes) -> int:
        response = self._request(
            "POST", "/api/v1/network/probe/upload", content=payload,
            headers={
                "Authorization": f"Bearer {credentials.access_token}",
                "Content-Type": "application/octet-stream",
            },
        )
        data = self._json_object(response)
        try:
            return int(data["received_bytes"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiClientError("The upload probe response was invalid.") from exc

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiClientError("The StreamML API is unavailable.") from exc
        if response.is_redirect:
            raise ApiClientError("The StreamML API unexpectedly returned a redirect.")
        if response.status_code >= 400:
            raise ApiClientError(f"The StreamML API returned HTTP {response.status_code}.")
        return response

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise ApiClientError("The StreamML API returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise ApiClientError("The StreamML API response must be a JSON object.")
        return data


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
