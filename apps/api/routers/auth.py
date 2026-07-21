"""Autenticación de usuarios basada en cookies."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from apps.api.dependencies import client_ip, current_user
from apps.api.schemas import LoginRequest
from src.streamml.observability.logging import audit_log
from src.streamml.security.auth import normalize_email
from src.streamml.security.crypto import hash_token, random_token, verify_password


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    database = request.app.state.database
    settings = request.app.state.settings
    ip = client_ip(request)
    if not request.app.state.rate_limiter.allow(f"login:{ip}", settings.login_limit, settings.rate_window_seconds):
        database.record_audit(actor_type="anonymous", action="auth.login", outcome="rate_limited", client_ip=ip)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos.")
    try:
        email = normalize_email(payload.email)
    except ValueError:
        email = payload.email.strip().lower()
    user = database.get_user_by_email(email)
    valid = bool(user) and verify_password(payload.password.get_secret_value(), user["password_hash"])
    if not valid:
        database.record_audit(
            actor_type="anonymous",
            action="auth.login",
            outcome="denied",
            client_ip=ip,
            details={"email_sha256": hashlib.sha256(email.encode("utf-8")).hexdigest()},
        )
        audit_log("auth.login.denied", client_ip=ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas.")
    token = random_token()
    database.save_auth_token(user["id"], hash_token(token), settings.session_ttl_seconds)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    database.record_audit(user_id=user["id"], actor_type="user", action="auth.login", outcome="success", client_ip=ip)
    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user.get("display_name") or user["email"],
        },
        "authenticated": True,
    }


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user.get("display_name") or user["email"],
        },
        "authenticated": True,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, user: dict = Depends(current_user)) -> Response:
    settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        request.app.state.database.revoke_auth_token(hash_token(token))
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.cookie_secure, httponly=True)
    request.app.state.database.record_audit(
        user_id=user["id"], actor_type="user", action="auth.logout", outcome="success", client_ip=client_ip(request)
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
