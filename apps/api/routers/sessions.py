"""Tenant-scoped transmission sessions."""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, status

from apps.api.dependencies import client_ip, current_user, require_owned_session
from apps.api.schemas import SessionCreate
from apps.api.routers.streams import stream_payload


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _public_session(session: dict) -> dict:
    return {key: value for key, value in session.items() if key not in {"user_id", "stream_id"}}


def _vdo_ninja(request: Request, session: dict) -> dict:
    seed = f"vdo:{session['user_id']}:{session['id']}".encode("utf-8")
    room_id = hmac.new(
        request.app.state.settings.media_auth_secret.encode("utf-8"), seed, hashlib.sha256
    ).hexdigest()[:32]
    encoded = quote(room_id, safe="")
    return {
        "phone_url": f"https://vdo.ninja/?push={encoded}&webcam&autostart",
        "embed_url": f"https://vdo.ninja/?view={encoded}&cleanoutput&autostart",
        "expires_at": None,
    }


def _detail_response(request: Request, session: dict, *, include_private_links: bool) -> dict:
    public = _public_session(session)
    if include_private_links:
        public["vdo_ninja"] = _vdo_ninja(request, session)
        public["stream"] = stream_payload(request, session)
    return public


@router.post("", status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, request: Request, user: dict = Depends(current_user)) -> dict:
    session = request.app.state.database.create_session(user["id"], payload.name)
    request.app.state.database.record_audit(
        user_id=user["id"], actor_type="user", action="session.create", resource_type="session",
        resource_id=session["id"], outcome="success", client_ip=client_ip(request),
    )
    return _detail_response(request, session, include_private_links=True)


@router.get("")
def list_sessions(request: Request, user: dict = Depends(current_user)) -> dict:
    items = []
    for row in request.app.state.database.list_sessions(user["id"]):
        detail = request.app.state.session_store.detail(user["id"], row["id"]) or row
        items.append(_detail_response(request, detail, include_private_links=False))
    return {"items": items, "total": len(items)}


@router.get("/{session_id}")
def get_session(session_id: str, request: Request, user: dict = Depends(current_user)) -> dict:
    require_owned_session(request, user, session_id)
    detail = request.app.state.session_store.detail(user["id"], session_id)
    return _detail_response(request, detail or {}, include_private_links=True)
