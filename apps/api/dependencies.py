"""Dependencias de FastAPI y guardias de autenticación por tenant."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, WebSocket, status

from src.streamml.security.crypto import hash_token


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def current_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get(request.app.state.settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida.")
    user = request.app.state.database.user_from_token_hash(hash_token(token))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida.")
    return user


def current_connector(request: Request) -> dict[str, Any]:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere autenticación de conector.")
    connector = request.app.state.database.connector_from_token_hash(hash_token(token))
    if not connector:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere autenticación de conector.")
    return connector


def websocket_user(websocket: WebSocket) -> dict[str, Any] | None:
    token = websocket.cookies.get(websocket.app.state.settings.session_cookie_name)
    if not token:
        return None
    return websocket.app.state.database.user_from_token_hash(hash_token(token))


def require_owned_session(request: Request, user: dict[str, Any], session_id: str) -> dict[str, Any]:
    session = request.app.state.database.get_session(user["id"], session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada.")
    return session
