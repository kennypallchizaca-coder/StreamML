"""Single-process authenticated WebSocket fan-out."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class WebSocketHub:
    def __init__(self) -> None:
        self._queues: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._queues[session_id].add(queue)
        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            subscribers = self._queues.get(session_id)
            if subscribers:
                subscribers.discard(queue)
                if not subscribers:
                    self._queues.pop(session_id, None)

    async def publish(self, session_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            subscribers = list(self._queues.get(session_id, ()))
        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)
