"""Low-duty-cycle network path measurement for model-compatible telemetry."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import statistics
import time
from typing import Callable

from .api_client import ApiClientError, StreamMLApiClient
from .secrets import ConnectorCredentials


@dataclass(frozen=True, slots=True)
class NetworkMeasurement:
    source: str
    upload_mbps: float
    download_mbps: float
    latency_ms: float
    jitter_ms: float
    packet_loss_percent: float
    connection_capacity_mbps: float

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


class NetworkProbe:
    """Measure the same connector-to-server path without using OBS bitrate."""

    def __init__(
        self,
        api: StreamMLApiClient,
        credentials: ConnectorCredentials,
        payload_bytes: int,
        *,
        monotonic: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._api = api
        self._credentials = credentials
        self._payload = b"StreamML" * (payload_bytes // 8) + b"S" * (payload_bytes % 8)
        self._monotonic = monotonic
        self._latencies: deque[float] = deque(maxlen=20)
        self._outcomes: deque[bool] = deque(maxlen=20)
        self._last: NetworkMeasurement | None = None

    @property
    def payload_bytes(self) -> int:
        return len(self._payload)

    def measure(self) -> NetworkMeasurement | None:
        try:
            latency_ms = self._latency()
            download_mbps = self._download()
            upload_mbps = self._upload()
        except ApiClientError:
            self._outcomes.append(False)
            return self._with_current_loss(self._last)
        self._outcomes.append(True)
        self._latencies.append(latency_ms)
        jitter = (
            statistics.fmean(
                abs(right - left)
                for left, right in zip(self._latencies, list(self._latencies)[1:])
            )
            if len(self._latencies) > 1
            else 0.0
        )
        measurement = NetworkMeasurement(
            source="streamml_http_probe",
            upload_mbps=round(upload_mbps, 3),
            download_mbps=round(download_mbps, 3),
            latency_ms=round(latency_ms, 3),
            jitter_ms=round(jitter, 3),
            packet_loss_percent=self._loss_percent(),
            connection_capacity_mbps=round(upload_mbps, 3),
        )
        self._last = measurement
        return measurement

    def _latency(self) -> float:
        started = self._monotonic()
        self._api.probe_latency(self._credentials)
        return (self._monotonic() - started) * 1000.0

    def _download(self) -> float:
        started = self._monotonic()
        received = self._api.probe_download(self._credentials, len(self._payload))
        elapsed = self._monotonic() - started
        if elapsed <= 0 or received != len(self._payload):
            raise ApiClientError("The download probe was incomplete.")
        return received * 8.0 / elapsed / 1_000_000.0

    def _upload(self) -> float:
        started = self._monotonic()
        received = self._api.probe_upload(self._credentials, self._payload)
        elapsed = self._monotonic() - started
        if elapsed <= 0 or received != len(self._payload):
            raise ApiClientError("The upload probe was incomplete.")
        return received * 8.0 / elapsed / 1_000_000.0

    def _loss_percent(self) -> float:
        return round(100.0 * (1.0 - sum(self._outcomes) / len(self._outcomes)), 3)

    def _with_current_loss(
        self, value: NetworkMeasurement | None
    ) -> NetworkMeasurement | None:
        if value is None:
            return None
        updated = NetworkMeasurement(
            source=value.source,
            upload_mbps=value.upload_mbps,
            download_mbps=value.download_mbps,
            latency_ms=value.latency_ms,
            jitter_ms=value.jitter_ms,
            packet_loss_percent=self._loss_percent(),
            connection_capacity_mbps=value.connection_capacity_mbps,
        )
        self._last = updated
        return updated
