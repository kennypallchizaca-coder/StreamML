"""Verified MediaMTX path status through its private Docker API."""

from __future__ import annotations

import json
from threading import Lock
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen


def media_path_state(payload: dict[str, Any]) -> str:
    """Translate a MediaMTX API response without inferring a false positive."""

    if payload.get("ready") is True or payload.get("available") is True or payload.get("online") is True:
        return "connected"
    return "waiting"


def _fetch_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310 - URL is deployment configuration.
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MediaMTX API returned an invalid response.")
    return payload


class MediaMtxStatusClient:
    """Small, bounded cache so telemetry never polls the media server per event."""

    def __init__(
        self,
        api_url: str,
        *,
        cache_seconds: float = 2.0,
        timeout_seconds: float = 0.5,
        fetch_json: Callable[[str, float], dict[str, Any]] = _fetch_json,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.cache_seconds = cache_seconds
        self.timeout_seconds = timeout_seconds
        self._fetch_json = fetch_json
        self._cache: dict[str, tuple[float, str]] = {}
        self._lock = Lock()

    def status_for_path(self, stream_id: str | None) -> str:
        if not stream_id or not self.api_url:
            return "unverified"
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(stream_id)
            if cached and now - cached[0] < self.cache_seconds:
                return cached[1]

        url = f"{self.api_url}/v3/paths/get/{quote(stream_id, safe='')}"
        try:
            state = media_path_state(self._fetch_json(url, self.timeout_seconds))
        except HTTPError as exc:
            state = "disconnected" if exc.code == 404 else "unverified"
        except (OSError, TimeoutError, URLError, ValueError, json.JSONDecodeError):
            state = "unverified"

        with self._lock:
            self._cache[stream_id] = (now, state)
        return state
