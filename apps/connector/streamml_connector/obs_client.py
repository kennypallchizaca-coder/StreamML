"""OBS WebSocket 5.x telemetry and narrowly-scoped control adapter."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import time
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import obsws_python as obs

from .config import ConnectorConfig


@dataclass(frozen=True, slots=True)
class ObsSnapshot:
    observed_at: str
    obs_connected: bool
    stream_active: bool | None
    stream_reconnecting: bool | None
    active_fps: float | None
    render_skipped_frames: int | None
    render_total_frames: int | None
    output_skipped_frames: int | None
    output_total_frames: int | None
    output_congestion: float | None
    output_bytes: int | None
    output_bitrate_kbps: float | None
    latency_ms: None = None
    packet_loss_percent: None = None

    def metrics(self) -> dict[str, Any]:
        """Return telemetry with unsupported network variables explicitly null."""

        return asdict(self)

    @classmethod
    def disconnected(cls) -> "ObsSnapshot":
        return cls(
            observed_at=_utc_now(),
            obs_connected=False,
            stream_active=None,
            stream_reconnecting=None,
            active_fps=None,
            render_skipped_frames=None,
            render_total_frames=None,
            output_skipped_frames=None,
            output_total_frames=None,
            output_congestion=None,
            output_bytes=None,
            output_bitrate_kbps=None,
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rtmp_stream_name(stream_key: str) -> str:
    """Return the stable MediaMTX path without exposing the publish token."""

    return stream_key.partition("?")[0]


def _publish_token_is_fresh(stream_key: str, *, minimum_remaining_seconds: float = 120.0) -> bool:
    """Check only the expiry of the opaque signed publish token.

    The API mints a fresh signed token on each settings request. Its signature
    remains validated by MediaMTX; decoding here only prevents an unnecessary
    OBS restart while a currently configured token is still valid.
    """

    token = parse_qs(stream_key.partition("?")[2], keep_blank_values=False).get("token", [""])[0]
    try:
        encoded = token.split(".", 1)[0]
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        expires_at = int(json.loads(raw.decode("utf-8"))["exp"])
    except (IndexError, KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return expires_at > time.time() + minimum_remaining_seconds


class ObsClient:
    """OBS client restricted to telemetry and explicit StreamML actions.

    Control calls are only reached through authenticated, session-scoped API
    commands.
    """

    ALLOWED_REQUESTS = frozenset(
        {
            "GetStats",
            "GetStreamStatus",
            "GetSceneList",
            "GetSceneItemList",
            "GetInputSettings",
            "SetInputSettings",
            "SetProfileParameter",
            "GetStreamServiceSettings",
            "SetStreamServiceSettings",
            "StopStream",
            "StartStream",
            "SetCurrentProgramScene",
        }
    )

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        client_factory: Callable[..., Any] = obs.ReqClient,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._client_factory = client_factory
        self._monotonic = monotonic
        self._sleeper = sleeper
        self._client: Any | None = None
        self._live_scene = config.live_scene
        self._backup_scene = config.backup_scene
        self._previous_output_bytes: int | None = None
        self._previous_sample_time: float | None = None
        self._rtmp_server: str | None = None
        self._rtmp_stream_key: str | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    def connect(self, password: str) -> None:
        self.disconnect()
        self._client = self._client_factory(
            host=self._config.obs_host,
            port=self._config.obs_port,
            password=password,
            timeout=self._config.request_timeout_seconds,
        )
        self._previous_output_bytes = None
        self._previous_sample_time = None

    def set_scene_names(self, *, live_scene: str, backup_scene: str) -> None:
        """Apply validated server-side defaults without exposing OBS credentials."""

        cleaned_live = live_scene.strip()
        cleaned_backup = backup_scene.strip()
        if not cleaned_live or not cleaned_backup:
            raise ValueError("OBS scene names cannot be blank.")
        self._live_scene = cleaned_live
        self._backup_scene = cleaned_backup

    def ensure_rtmp_service(self, server: str, stream_key: str) -> bool:
        """Synchronize the paired session's RTMP target without browser copy/paste."""

        if self._client is None:
            raise RuntimeError("OBS is not connected.")
        if not server.startswith(("rtmp://", "rtmps://")) or not stream_key:
            raise ValueError("Invalid RTMP service settings.")
        if self._rtmp_server == server and self._rtmp_stream_key == stream_key:
            return False

        response = self._client.get_stream_service_settings()
        current = getattr(response, "stream_service_settings", {}) or {}
        if not isinstance(current, dict):
            current = {}
        current_server = str(current.get("server") or "").strip()
        current_key = str(current.get("key") or "")
        # OBS canonicalizes a bare RTMP endpoint with a trailing slash. Treat
        # both representations as the same destination; otherwise the
        # settings refresh would restart an already healthy output every few
        # seconds, preventing MediaMTX/HLS from becoming ready.
        if current_server.rstrip("/") == server.rstrip("/"):
            same_destination_with_valid_token = (
                _rtmp_stream_name(current_key) == _rtmp_stream_name(stream_key) and _publish_token_is_fresh(current_key)
            )
            if current_key == stream_key or same_destination_with_valid_token:
                self._rtmp_server = server
                self._rtmp_stream_key = current_key
                return False

        was_streaming = bool(getattr(self._client.get_stream_status(), "output_active", False))
        # OBS explicitly rejects SetStreamServiceSettings while output is
        # active.  Switch in this order so moving to a newly-paired session
        # never leaves the operator to edit or restart OBS manually.
        if was_streaming:
            self._stop_stream_output()
        try:
            self._client.set_stream_service_settings("rtmp_custom", {"server": server, "key": stream_key})
        except Exception:
            # Preserve the existing live output when OBS rejects the new
            # target for a transient reason. The original exception is still
            # propagated so the connector can retry with bounded backoff.
            if was_streaming:
                try:
                    self._client.start_stream()
                except Exception:
                    pass
            raise
        self._rtmp_server = server
        self._rtmp_stream_key = stream_key
        if was_streaming:
            self._client.start_stream()
        return True

    def _stop_stream_output(self) -> None:
        """Stop OBS output and wait briefly for a safe RTMP target switch."""

        if self._client is None:
            raise RuntimeError("OBS is not connected.")
        self._client.stop_stream()
        deadline = self._monotonic() + 5.0
        while bool(getattr(self._client.get_stream_status(), "output_active", False)):
            if self._monotonic() >= deadline:
                raise RuntimeError("OBS did not stop the previous RTMP output in time.")
            self._sleeper(0.2)

    def collect(self) -> ObsSnapshot:
        if self._client is None:
            raise RuntimeError("OBS is not connected.")

        # Keep this explicit: these are the only two OBS requests permitted.
        stats = self._client.get_stats()
        status = self._client.get_stream_status()
        now = self._monotonic()
        output_bytes = int(status.output_bytes)
        bitrate = self._derive_output_bitrate(output_bytes, now, bool(status.output_active))

        return ObsSnapshot(
            observed_at=_utc_now(),
            obs_connected=True,
            stream_active=bool(status.output_active),
            stream_reconnecting=bool(status.output_reconnecting),
            active_fps=float(stats.active_fps),
            render_skipped_frames=int(stats.render_skipped_frames),
            render_total_frames=int(stats.render_total_frames),
            output_skipped_frames=int(status.output_skipped_frames),
            output_total_frames=int(status.output_total_frames),
            output_congestion=float(status.output_congestion),
            output_bytes=output_bytes,
            # Derived strictly from OBS output byte counter; this is not network capacity.
            output_bitrate_kbps=bitrate,
        )

    def validate_scenes(self) -> list[str]:
        """Return required scene names missing from the connected OBS instance."""

        if self._client is None:
            raise RuntimeError("OBS is not connected.")
        response = self._client.get_scene_list()
        names: set[str] = set()
        for scene in getattr(response, "scenes", ()):
            if isinstance(scene, dict):
                name = scene.get("sceneName") or scene.get("scene_name")
            else:
                name = getattr(scene, "scene_name", None) or getattr(scene, "sceneName", None)
            if name:
                names.add(str(name))
        return [name for name in (self._live_scene, self._backup_scene) if name not in names]

    def ensure_vdo_bridge(self, bridge_url: str) -> str | None:
        """Configure an unambiguous live Browser Source with the scoped bridge."""

        if self._client is None:
            raise RuntimeError("OBS is not connected.")
        parsed = urlparse(bridge_url)
        loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or (parsed.scheme != "https" and not loopback)
            or not parsed.path.startswith("/vdo-bridge/")
            or parsed.username
            or parsed.password
        ):
            raise ValueError("The VDO bridge URL is outside the allowed security boundary.")

        response = self._client.get_scene_item_list(self._live_scene)
        browser_sources: list[str] = []
        for item in getattr(response, "scene_items", ()):
            if isinstance(item, dict):
                name = item.get("sourceName") or item.get("source_name")
                kind = item.get("inputKind") or item.get("input_kind")
            else:
                name = getattr(item, "source_name", None) or getattr(item, "sourceName", None)
                kind = getattr(item, "input_kind", None) or getattr(item, "inputKind", None)
            if name and kind == "browser_source":
                browser_sources.append(str(name))
        for name in browser_sources:
            settings = self._client.get_input_settings(name)
            values = getattr(settings, "input_settings", {})
            if isinstance(values, dict) and values.get("url") == bridge_url:
                return name
        if len(browser_sources) != 1:
            return None
        name = browser_sources[0]
        self._client.set_input_settings(name, {"url": bridge_url}, True)
        return name

    def _derive_output_bitrate(self, output_bytes: int, sample_time: float, stream_active: bool) -> float | None:
        bitrate: float | None = None
        if (
            stream_active
            and self._previous_output_bytes is not None
            and self._previous_sample_time is not None
            and output_bytes >= self._previous_output_bytes
        ):
            elapsed = sample_time - self._previous_sample_time
            if elapsed > 0:
                bitrate = (output_bytes - self._previous_output_bytes) * 8.0 / elapsed / 1000.0

        self._previous_output_bytes = output_bytes
        self._previous_sample_time = sample_time
        return None if bitrate is None else round(bitrate, 3)

    def apply_command(self, command: dict[str, Any]) -> None:
        """Apply one validated server command or fail without partial ambiguity."""

        if self._client is None:
            raise RuntimeError("OBS is not connected.")
        command_type = command.get("command_type")
        payload = command.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("Control command payload must be an object.")
        if command_type == "set_profile":
            self._apply_profile(payload)
            return
        if command_type == "activate_backup":
            self._client.set_current_program_scene(self._backup_scene)
            return
        if command_type == "restore_live":
            self._client.set_current_program_scene(self._live_scene)
            return
        raise ValueError("Unsupported control command.")

    def _apply_profile(self, payload: dict[str, Any]) -> None:
        profile = payload.get("profile")
        spec = payload.get("spec")
        if profile not in {"low", "medium", "high"} or not isinstance(spec, dict):
            raise ValueError("Invalid StreamML profile command.")
        required = {"width", "height", "fps", "video_bitrate_kbps", "audio_bitrate_kbps"}
        if not required.issubset(spec):
            raise ValueError("Profile specification is incomplete.")
        values = {name: int(spec[name]) for name in required}
        if any(value <= 0 for value in values.values()):
            raise ValueError("Profile values must be positive.")

        # OBS stores these values in the active profile.  Encoder bitrate is
        # updated first, followed by scaled output size and frame rate.
        parameters = (
            ("SimpleOutput", "VBitrate", values["video_bitrate_kbps"]),
            ("SimpleOutput", "ABitrate", values["audio_bitrate_kbps"]),
            ("Video", "OutputCX", values["width"]),
            ("Video", "OutputCY", values["height"]),
            ("Video", "FPSCommon", values["fps"]),
        )
        for category, name, value in parameters:
            self._client.set_profile_parameter(category, name, str(value))

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()
            finally:
                self._client = None
        self._previous_output_bytes = None
        self._previous_sample_time = None
        self._rtmp_server = None
        self._rtmp_stream_key = None


# Backward-compatible import for integrations built before authenticated OBS
# control was introduced. New code should use ``ObsClient``.
ReadOnlyObsClient = ObsClient
