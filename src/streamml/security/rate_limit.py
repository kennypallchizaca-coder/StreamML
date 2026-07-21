"""Limitador de tasa de ventana fija local al proceso."""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
import time


class RateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                del self._events[key]
                if limit <= 0:
                    return False
                self._events[key].append(now)
                return True
            if len(events) >= limit:
                return False
            events.append(now)
            return True
