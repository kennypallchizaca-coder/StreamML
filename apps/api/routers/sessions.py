"""Tenant-scoped transmission sessions."""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, status

from apps.api.dependencies import client_ip, current_user, require_owned_session
from apps.api.schemas import SessionCreate
from apps.api.routers.streams import stream_payload
from src.streamml.security.vdo import vdo_bridge_token


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _public_session(session: dict) -> dict:
    return {key: value for key, value in session.items() if key not in {"user_id", "stream_id"}}


def _vdo_ninja(request: Request, session: dict) -> dict:
    seed = f"vdo:{session['user_id']}:{session['id']}".encode("utf-8")
    room_id = hmac.new(request.app.state.settings.media_auth_secret.encode("utf-8"), seed, hashlib.sha256).hexdigest()[
        :32
    ]
    encoded = quote(room_id, safe="")
    remote_id = hmac.new(
        request.app.state.settings.media_auth_secret.encode("utf-8"),
        f"vdo-remote:{session['user_id']}:{session['id']}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:24]
    remote = quote(remote_id, safe="")
    generated = {
        "phone_url": f"https://vdo.ninja/?push={encoded}&webcam&autostart&remote={remote}",
        "embed_url": f"https://vdo.ninja/?view={encoded}&cleanoutput&autostart&remote={remote}",
        "expires_at": None,
    }
    external_embed_url = session.get("configuration", {}).get("vdo_embed_url")
    if isinstance(external_embed_url, str) and external_embed_url:
        generated["embed_url"] = external_embed_url
        generated["source"] = "external"
    else:
        generated["source"] = "streamml"
    request_origin = (request.headers.get("origin") or "").rstrip("/")
    frontend_origin = (
        request_origin
        if request_origin in request.app.state.settings.allowed_origins
        else request.app.state.settings.allowed_origins[0]
    )
    bridge_token = vdo_bridge_token(request.app.state.settings.media_auth_secret, session["id"])
    generated["bridge_url"] = (
        f"{frontend_origin}/vdo-bridge/{quote(session['id'], safe='')}?token={quote(bridge_token, safe='')}"
    )
    return generated


def _detail_response(request: Request, session: dict, *, include_private_links: bool) -> dict:
    public = _public_session(session)
    if include_private_links:
        public["vdo_ninja"] = _vdo_ninja(request, session)
        public["stream"] = stream_payload(request, session)
    return public


@router.post("", status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, request: Request, user: dict = Depends(current_user)) -> dict:
    defaults = request.app.state.database.get_user_settings(user["id"])["stream"]
    session = request.app.state.database.create_session(
        user["id"],
        payload.name,
        {
            "platform": payload.platform or defaults["platform"],
            "resolution": payload.resolution or defaults["preferred_resolution"],
            "initial_profile": defaults["preferred_profile"],
            "planned_duration_hours": payload.planned_duration_hours,
            "connection_type": payload.connection_type,
        },
    )
    request.app.state.database.record_audit(
        user_id=user["id"],
        actor_type="user",
        action="session.create",
        resource_type="session",
        resource_id=session["id"],
        outcome="success",
        client_ip=client_ip(request),
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
