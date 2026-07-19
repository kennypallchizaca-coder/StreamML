"""Authenticated, tenant-scoped real-time session updates."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from apps.api.dependencies import websocket_user


router = APIRouter(tags=["websocket"])


@router.websocket("/ws/sessions/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str) -> None:
    settings = websocket.app.state.settings
    origin = (websocket.headers.get("origin") or "").rstrip("/")
    if origin not in settings.allowed_origins:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user = websocket_user(websocket)
    if not user or not websocket.app.state.database.get_session(user["id"], session_id):
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    queue = await websocket.app.state.websocket_hub.subscribe(session_id)
    try:
        snapshot = websocket.app.state.session_store.detail(user["id"], session_id)
        await websocket.send_json({"type": "snapshot", "session_id": session_id, "session": snapshot})
        receive_task = asyncio.create_task(websocket.receive_text())
        queue_task = asyncio.create_task(queue.get())
        while True:
            done, _pending = await asyncio.wait({receive_task, queue_task}, return_when=asyncio.FIRST_COMPLETED)
            if receive_task in done:
                message = receive_task.result()
                if message == "ping":
                    await websocket.send_json({"type": "pong"})
                receive_task = asyncio.create_task(websocket.receive_text())
            if queue_task in done:
                await websocket.send_json(queue_task.result())
                queue_task = asyncio.create_task(queue.get())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        for task in (locals().get("receive_task"), locals().get("queue_task")):
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError, WebSocketDisconnect):
                    await task
        await websocket.app.state.websocket_hub.unsubscribe(session_id, queue)
