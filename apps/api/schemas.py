"""Strict Pydantic transport schemas for the public API."""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Literal
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

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Session name cannot be blank.")
        return cleaned


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


class TelemetryRequest(StrictModel):
    session_id: str
    source: Literal["obs_websocket_5"]
    observed_at: str
    sequence: int = Field(ge=0)
    metrics: ObsMetrics
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
