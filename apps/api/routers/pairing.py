"""Temporary, one-use connector pairing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status

from apps.api.dependencies import client_ip, current_user, require_owned_session
from apps.api.schemas import ConnectorLink, PairingCodeCreate
from src.streamml.security.crypto import hash_pairing_code, hash_token, random_token


router = APIRouter(tags=["pairing"])
PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _new_code() -> str:
    return "".join(secrets.choice(PAIRING_ALPHABET) for _ in range(10))


@router.post("/api/v1/pairing/codes", status_code=status.HTTP_201_CREATED)
@router.post("/api/v1/connectors/pairing-codes", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_pairing_code(payload: PairingCodeCreate, request: Request, user: dict = Depends(current_user)) -> dict:
    settings = request.app.state.settings
    require_owned_session(request, user, payload.session_id)
    if not request.app.state.rate_limiter.allow(
        f"pairing-create:{user['id']}", settings.pairing_limit, settings.rate_window_seconds
    ):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts.")
    code = _new_code()
    code_hash = hash_pairing_code(code, settings.token_secret)
    pairing_id = request.app.state.database.create_pairing_code(
        user["id"], payload.session_id, code_hash, settings.pairing_ttl_seconds
    )
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=settings.pairing_ttl_seconds)).isoformat()
    request.app.state.database.record_audit(
        user_id=user["id"],
        actor_type="user",
        action="connector.pairing_code.create",
        resource_type="pairing_code",
        resource_id=pairing_id,
        outcome="success",
        client_ip=client_ip(request),
    )
    return {"code": code, "expires_at": expires_at, "session_id": payload.session_id}


@router.post("/api/v1/connectors/link")
@router.post("/api/v1/pairing/link", include_in_schema=False)
def link_connector(payload: ConnectorLink, request: Request) -> dict:
    settings = request.app.state.settings
    ip = client_ip(request)
    if not request.app.state.rate_limiter.allow(
        f"pairing-link:{ip}", settings.pairing_limit, settings.rate_window_seconds
    ):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts.")
    access_token = random_token()
    connector = request.app.state.database.consume_pairing_code(
        hash_pairing_code(payload.code, settings.token_secret),
        payload.connector_name.strip(),
        payload.connector_version.strip(),
        hash_token(access_token),
        settings.connector_ttl_seconds,
    )
    if not connector:
        request.app.state.database.record_audit(
            actor_type="connector", action="connector.link", outcome="denied", client_ip=ip
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired pairing code.")
    request.app.state.database.record_audit(
        user_id=connector["user_id"],
        actor_type="connector",
        action="connector.link",
        resource_type="connector",
        resource_id=connector["id"],
        outcome="success",
        client_ip=ip,
    )
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "connector_id": connector["id"],
        "session_id": connector["session_id"],
    }
