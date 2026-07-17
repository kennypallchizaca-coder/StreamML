"""Strictly read-only OBS WebSocket 5.x adapter."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import time
from typing import Any, Callable

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


class ReadOnlyObsClient:
    """OBS client whose public surface contains no control operation.

    The only OBS RPCs invoked are ``GetStats`` and ``GetStreamStatus``. The
    obsws-python constructor performs the protocol's authenticated Identify
    handshake; it receives the password in memory and never sends it to StreamML.
    """

    ALLOWED_REQUESTS = frozenset({"GetStats", "GetStreamStatus"})

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        client_factory: Callable[..., Any] = obs.ReqClient,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._client_factory = client_factory
        self._monotonic = monotonic
        self._client: Any | None = None
        self._previous_output_bytes: int | None = None
        self._previous_sample_time: float | None = None

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

    def _derive_output_bitrate(
        self, output_bytes: int, sample_time: float, stream_active: bool
    ) -> float | None:
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

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()
            finally:
                self._client = None
        self._previous_output_bytes = None
        self._previous_sample_time = None

