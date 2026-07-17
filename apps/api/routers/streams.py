"""Tenant-scoped MediaMTX URLs and internal authorization callback."""

from __future__ import annotations

import base64
import hmac
import ipaddress
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from apps.api.dependencies import current_user, require_owned_session
from apps.api.schemas import MediaMtxAuthRequest
from src.streamml.security.crypto import sign_scoped_token, verify_scoped_token


router = APIRouter(tags=["streams"])


def _valid_internal_auth(request: Request, configured_secret: str, header_secret: str | None) -> bool:
    if header_secret and hmac.compare_digest(header_secret, configured_secret):
        return True
    authorization = request.headers.get("authorization", "")
    scheme, _, encoded = authorization.partition(" ")
    if scheme.lower() == "basic" and encoded:
        try:
            username, supplied = base64.b64decode(encoded, validate=True).decode("utf-8").split(":", 1)
        except (ValueError, UnicodeDecodeError):
            return False
        return username == "mediamtx" and hmac.compare_digest(supplied, configured_secret)
    try:
        return bool(request.client) and ipaddress.ip_address(request.client.host).is_private
    except ValueError:
        return False


def _media_token(request: Request, session: dict, scope: str) -> str:
    return sign_scoped_token(
        {
            "user_id": session["user_id"],
            "session_id": session["id"],
            "stream_id": session["stream_id"],
            "scope": scope,
        },
        request.app.state.settings.token_secret,
        ttl_seconds=15 * 60,
    )


def stream_payload(request: Request, session: dict) -> dict:
    base = request.app.state.settings.mediamtx_public_base
    read_token = _media_token(request, session, "read")
    publish_token = _media_token(request, session, "publish")
    stream_id = session["stream_id"]
    rtmp_base = request.app.state.settings.mediamtx_rtmp_publish_base
    return {
        "session_id": session["id"],
        "stream_id": stream_id,
        "status": session["status"],
        "webrtc_url": f"{base}/{stream_id}/whep?token={read_token}",
        "hls_url": f"{base}/{stream_id}/index.m3u8?token={read_token}",
        "whip_publish_url": f"{base}/{stream_id}/whip?token={publish_token}",
        "rtmp_publish_url": f"{rtmp_base}/{stream_id}?token={publish_token}" if rtmp_base else None,
        "tokens_expire_seconds": 15 * 60,
    }


@router.get("/api/v1/streams/{session_id}")
def get_stream(session_id: str, request: Request, user: dict = Depends(current_user)) -> dict:
    return stream_payload(request, require_owned_session(request, user, session_id))


@router.post("/api/v1/internal/mediamtx/auth", include_in_schema=False)
def authorize_mediamtx(
    payload: MediaMtxAuthRequest,
    request: Request,
    x_streamml_media_secret: str | None = Header(default=None),
) -> dict:
    settings = request.app.state.settings
    if not _valid_internal_auth(request, settings.media_auth_secret, x_streamml_media_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")
    token = payload.token or payload.password
    if not token and payload.query:
        token = parse_qs(payload.query.lstrip("?"), keep_blank_values=False).get("token", [None])[0]
    claims = verify_scoped_token(token or "", settings.token_secret)
    action = payload.action.lower()
    required_scope = "publish" if action == "publish" else "read"
    path = payload.path.strip("/")
    if not claims or claims.get("scope") != required_scope or claims.get("stream_id") != path:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")
    session = request.app.state.database.get_session(str(claims.get("user_id")), str(claims.get("session_id")))
    if not session or session["stream_id"] != path:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")
    return {"authorized": True}
