"""Strict Pydantic transport schemas for the public API."""

from __future__ import annotations

from datetime import datetime
import math
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("A valid UUID is required.") from exc


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=1024)


class SessionCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    platform: Literal["youtube", "twitch", "facebook", "kick", "custom"] | None = None
    resolution: Literal["480p", "720p", "1080p"] | None = None
    planned_duration_hours: Literal["1", "2", "4", "8"] | None = None
    connection_type: Literal["cable", "wifi", "mobile"] | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Session name cannot be blank.")
        return cleaned


class AccountSettingsUpdate(StrictModel):
    display_name: str = Field(min_length=1, max_length=100)
    current_password: SecretStr | None = None
    new_password: SecretStr | None = Field(default=None, min_length=12, max_length=1024)

    @model_validator(mode="after")
    def password_change_is_complete(self) -> "AccountSettingsUpdate":
        if (self.current_password is None) != (self.new_password is None):
            raise ValueError("Current and new passwords are both required to change the password.")
        return self

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Display name cannot be blank.")
        return cleaned


class PreferencesSettingsUpdate(StrictModel):
    language: Literal["es"]
    timezone: Literal["auto", "America/Guayaquil", "UTC"]
    dark_mode: bool
    alert_detail: Literal["low", "normal", "high"]


class StreamSettingsUpdate(StrictModel):
    preferred_resolution: Literal["480p", "720p", "1080p"]
    preferred_profile: Literal["low", "medium", "high"]
    platform: Literal["youtube", "twitch", "facebook", "kick", "custom"]
    live_scene: str = Field(min_length=1, max_length=120)
    backup_scene: str = Field(min_length=1, max_length=120)
    network_probe_interval_seconds: int = Field(ge=1, le=60)
    network_probe_bytes: int = Field(ge=1024, le=524288)

    @field_validator("live_scene", "backup_scene")
    @classmethod
    def clean_scene_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Scene name cannot be blank.")
        return cleaned

    @model_validator(mode="after")
    def scenes_are_distinct(self) -> "StreamSettingsUpdate":
        if self.live_scene.casefold() == self.backup_scene.casefold():
            raise ValueError("Live and backup scenes must use different names.")
        return self


class SessionVideoLinkUpdate(StrictModel):
    embed_url: str = Field(min_length=12, max_length=2048)


class DestructiveActionConfirmation(StrictModel):
    confirmation: str = Field(min_length=1, max_length=254)
    current_password: SecretStr | None = Field(default=None, max_length=1024)


class PairingCodeCreate(StrictModel):
    session_id: str

    @field_validator("session_id")
    @classmethod
    def valid_session_id(cls, value: str) -> str:
        return _uuid(value)


class ConnectorLink(StrictModel):
    code: str = Field(min_length=8, max_length=32)
    connector_name: str = Field(min_length=1, max_length=120)
    connector_version: str = Field(min_length=1, max_length=64)


class ControlCommandAck(StrictModel):
    success: bool
    error_message: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def error_matches_status(self) -> "ControlCommandAck":
        if self.success and self.error_message:
            raise ValueError("A successful command cannot include error_message.")
        if not self.success and not (self.error_message or "").strip():
            raise ValueError("A failed command must include error_message.")
        return self


class ObsMetrics(StrictModel):
    obs_connected: bool
    stream_active: bool | None = None
    stream_reconnecting: bool | None = None
    active_fps: float | int | None = None
    render_skipped_frames: int | None = Field(default=None, ge=0)
    render_total_frames: int | None = Field(default=None, ge=0)
    output_skipped_frames: int | None = Field(default=None, ge=0)
    output_total_frames: int | None = Field(default=None, ge=0)
    output_congestion: float | int | None = None
    output_bytes: int | None = Field(default=None, ge=0)
    output_bitrate_kbps: float | int | None = None

    @model_validator(mode="after")
    def finite_nonnegative(self) -> "ObsMetrics":
        for name in ("active_fps", "output_congestion", "output_bitrate_kbps"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(float(value)) or float(value) < 0):
                raise ValueError(f"{name} must be finite and non-negative.")
        return self


class UnsupportedMetrics(StrictModel):
    latency_ms: None = None
    packet_loss_percent: None = None
    upload_mbps: None = None
    download_mbps: None = None
    connection_capacity_mbps: None = None


class NetworkMetrics(StrictModel):
    """Network-path measurements; never derived from OBS output bitrate."""

    source: Literal["streamml_http_probe", "external_measurement"]
    upload_mbps: float | int = Field(ge=0)
    download_mbps: float | int = Field(ge=0)
    latency_ms: float | int = Field(ge=0)
    jitter_ms: float | int = Field(ge=0)
    packet_loss_percent: float | int = Field(ge=0, le=100)
    connection_capacity_mbps: float | int = Field(ge=0)

    @model_validator(mode="after")
    def finite_values(self) -> "NetworkMetrics":
        for name in (
            "upload_mbps",
            "download_mbps",
            "latency_ms",
            "jitter_ms",
            "packet_loss_percent",
            "connection_capacity_mbps",
        ):
            if not math.isfinite(float(getattr(self, name))):
                raise ValueError(f"{name} must be finite.")
        return self


class TelemetryRequest(StrictModel):
    session_id: str
    source: Literal["obs_websocket_5"]
    observed_at: str
    sequence: int = Field(ge=0)
    metrics: ObsMetrics
    network: NetworkMetrics | None = None
    unsupported: UnsupportedMetrics = Field(default_factory=UnsupportedMetrics)

    @field_validator("session_id")
    @classmethod
    def valid_session_id(cls, value: str) -> str:
        return _uuid(value)

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("observed_at must be an ISO-8601 datetime.") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("observed_at must include a timezone.")
        return parsed.isoformat()


class VdoNinjaMetrics(StrictModel):
    """Privacy-safe WebRTC measurements extracted by the VDO.Ninja bridge."""

    bitrate_kbps: float | int | None = Field(default=None, ge=0, le=100_000)
    available_outgoing_bitrate_kbps: float | int | None = Field(default=None, ge=0, le=100_000)
    packet_loss_percent: float | int | None = Field(default=None, ge=0, le=100)
    packets_lost: int | None = Field(default=None, ge=0)
    packets_received: int | None = Field(default=None, ge=0)
    jitter_ms: float | int | None = Field(default=None, ge=0, le=60_000)
    round_trip_time_ms: float | int | None = Field(default=None, ge=0, le=60_000)
    frames_per_second: float | int | None = Field(default=None, ge=0, le=240)
    frames_dropped: int | None = Field(default=None, ge=0)
    frames_received: int | None = Field(default=None, ge=0)
    frame_width: int | None = Field(default=None, ge=0, le=16_384)
    frame_height: int | None = Field(default=None, ge=0, le=16_384)

    @model_validator(mode="after")
    def finite_values(self) -> "VdoNinjaMetrics":
        for name in (
            "bitrate_kbps",
            "available_outgoing_bitrate_kbps",
            "packet_loss_percent",
            "jitter_ms",
            "round_trip_time_ms",
            "frames_per_second",
        ):
            value = getattr(self, name)
            if value is not None and not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite.")
        return self


class VdoNinjaTelemetryRequest(StrictModel):
    session_id: str
    source: Literal["vdo_ninja_iframe"]
    reporter_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    sequence: int = Field(ge=0)
    observed_at: str
    status: Literal["waiting", "connected", "disconnected", "error"]
    metrics: VdoNinjaMetrics = Field(default_factory=VdoNinjaMetrics)

    @field_validator("session_id")
    @classmethod
    def valid_session_id(cls, value: str) -> str:
        return _uuid(value)

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("observed_at must be an ISO-8601 datetime.") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("observed_at must include a timezone.")
        return parsed.isoformat()


class FeatureInput(StrictModel):
    name: str
    value: float | int
    unit: str
    source: str


class ReactivePredictionRequest(StrictModel):
    session_id: str
    features: list[FeatureInput]

    @field_validator("session_id")
    @classmethod
    def valid_session_id(cls, value: str) -> str:
        return _uuid(value)


class PredictiveSample(StrictModel):
    elapsed_seconds: float | int
    throughput_mbps: float | int
    unit: str
    source: str


class PredictivePredictionRequest(StrictModel):
    session_id: str
    samples: list[PredictiveSample]
    current_profile: int

    @field_validator("session_id")
    @classmethod
    def valid_session_id(cls, value: str) -> str:
        return _uuid(value)


class MediaMtxAuthRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    user: str | None = None
    password: str | None = None
    token: str | None = None
    action: str
    path: str
    protocol: str | None = None
    query: str | None = None


class ErrorResponse(StrictModel):
    message: str
    details: list[str] = Field(default_factory=list)
