"""Configuraciones persistentes, autenticadas, y controles de privacidad del usuario."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from apps.api.dependencies import client_ip, current_connector, current_user, require_owned_session
from apps.api.routers.sessions import _vdo_ninja
from apps.api.schemas import (
    AccountSettingsUpdate,
    DestructiveActionConfirmation,
    PreferencesSettingsUpdate,
    SessionVideoLinkUpdate,
    StreamSettingsUpdate,
)
from src.streamml.security.crypto import hash_token, verify_password


router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
connector_router = APIRouter(prefix="/api/v1/connectors", tags=["connector-settings"])


def _safe_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user.get("display_name") or user["email"],
    }


def _connector_view(connector: dict) -> dict:
    last_seen_at = connector.get("last_seen_at")
    connected = False
    if last_seen_at:
        try:
            seen = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
            connected = seen >= datetime.now(timezone.utc) - timedelta(minutes=2)
        except ValueError:
            connected = False
    return {
        "id": connector["id"],
        "session_id": connector["session_id"],
        "name": connector["name"],
        "version": connector["version"],
        "last_seen_at": last_seen_at,
        "connected": connected,
    }


def _settings_response(request: Request, user: dict) -> dict:
    database = request.app.state.database
    persisted = database.get_user_settings(user["id"])
    return {
        "user": _safe_user(database.get_user_by_id(user["id"]) or user),
        "preferences": persisted["preferences"],
        "stream": persisted["stream"],
        "updated_at": persisted["updated_at"],
        "connectors": [_connector_view(item) for item in database.list_connectors(user["id"])],
        "security": {
            "server_secrets_managed_externally": True,
            "message": (
                "Las contraseñas de OBS, claves RTMP y secretos del servidor no se almacenan "
                "en el navegador. Se administran de forma local o mediante variables seguras del servidor."
            ),
        },
    }


@router.get("")
def get_settings(request: Request, user: dict = Depends(current_user)) -> dict:
    return _settings_response(request, user)


@router.put("/account")
def update_account(payload: AccountSettingsUpdate, request: Request, user: dict = Depends(current_user)) -> dict:
    database = request.app.state.database
    current = database.get_user_by_id(user["id"])
    if not current:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida.")
    new_password = payload.new_password.get_secret_value() if payload.new_password else None
    if new_password is not None:
        if payload.current_password is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual es obligatoria.")
        if not verify_password(payload.current_password.get_secret_value(), current["password_hash"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta.")
    updated = database.update_user_profile(user["id"], display_name=payload.display_name, new_password=new_password)
    if new_password is not None:
        current_token = request.cookies.get(request.app.state.settings.session_cookie_name)
        if current_token:
            database.revoke_other_auth_tokens(user["id"], hash_token(current_token))
    database.record_audit(
        user_id=user["id"],
        actor_type="user",
        action="settings.account.update",
        outcome="success",
        client_ip=client_ip(request),
        details={"password_changed": new_password is not None},
    )
    return {"user": _safe_user(updated or user)}


@router.put("/preferences")
def update_preferences(
    payload: PreferencesSettingsUpdate, request: Request, user: dict = Depends(current_user)
) -> dict:
    result = request.app.state.database.update_user_settings(user["id"], preferences=payload.model_dump())
    request.app.state.database.record_audit(
        user_id=user["id"],
        actor_type="user",
        action="settings.preferences.update",
        outcome="success",
        client_ip=client_ip(request),
    )
    return {"preferences": result["preferences"], "updated_at": result["updated_at"]}


@router.put("/stream")
def update_stream_settings(payload: StreamSettingsUpdate, request: Request, user: dict = Depends(current_user)) -> dict:
    result = request.app.state.database.update_user_settings(user["id"], stream=payload.model_dump())
    request.app.state.database.record_audit(
        user_id=user["id"],
        actor_type="user",
        action="settings.stream.update",
        outcome="success",
        client_ip=client_ip(request),
    )
    return {"stream": result["stream"], "updated_at": result["updated_at"]}


@router.get("/export")
def export_data(request: Request, user: dict = Depends(current_user)) -> dict:
    request.app.state.database.record_audit(
        user_id=user["id"],
        actor_type="user",
        action="settings.data.export",
        outcome="success",
        client_ip=client_ip(request),
    )
    return request.app.state.database.export_user_data(user["id"])


@router.delete("/history")
def delete_history(
    payload: DestructiveActionConfirmation, request: Request, user: dict = Depends(current_user)
) -> dict:
    if payload.confirmation != "DELETE_HISTORY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Escribe DELETE_HISTORY para confirmar la eliminación del historial.",
        )
    deleted = request.app.state.database.delete_user_history(user["id"])
    request.app.state.database.record_audit(
        user_id=user["id"],
        actor_type="user",
        action="settings.history.delete",
        outcome="success",
        client_ip=client_ip(request),
        details={"sessions_deleted": deleted},
    )
    return {"deleted_sessions": deleted}


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: DestructiveActionConfirmation,
    request: Request,
    response: Response,
    user: dict = Depends(current_user),
) -> Response:
    if payload.confirmation != f"DELETE {user['email']}":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Escribe DELETE seguido de tu correo para confirmar la eliminación de la cuenta.",
        )
    if payload.current_password is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ingresa tu contraseña actual.")
    stored = request.app.state.database.get_user_by_id(user["id"])
    if not stored or not verify_password(payload.current_password.get_secret_value(), stored["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta.")
    request.app.state.database.record_audit(
        user_id=user["id"],
        actor_type="user",
        action="settings.account.delete",
        outcome="success",
        client_ip=client_ip(request),
    )
    request.app.state.database.delete_user(user["id"])
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


def _valid_vdo_embed_url(value: str) -> str:
    try:
        parsed = urlparse(value.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El enlace no es válido."
        ) from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"vdo.ninja", "www.vdo.ninja"}
        or parsed.username
        or parsed.password
        or "push=" in parsed.query
        or not ("view=" in parsed.query or "room=" in parsed.query)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Usa un enlace HTTPS de visualización o sala de VDO.Ninja, no el enlace de emisión del teléfono.",
        )
    return parsed.geturl()


@router.put("/sessions/{session_id}/video-link")
def update_video_link(
    session_id: str, payload: SessionVideoLinkUpdate, request: Request, user: dict = Depends(current_user)
) -> dict:
    require_owned_session(request, user, session_id)
    url = _valid_vdo_embed_url(payload.embed_url)
    updated = request.app.state.database.update_session_configuration(user["id"], session_id, {"vdo_embed_url": url})
    request.app.state.database.record_audit(
        user_id=user["id"],
        actor_type="user",
        action="session.video_link.update",
        outcome="success",
        resource_type="session",
        resource_id=session_id,
        client_ip=client_ip(request),
    )
    return {"session_id": session_id, "embed_url": updated["configuration"]["vdo_embed_url"]}


@connector_router.get("/settings")
def connector_settings(request: Request, connector: dict = Depends(current_connector)) -> dict:
    stream = request.app.state.database.get_user_settings(connector["user_id"])["stream"]
    session = request.app.state.database.get_session(connector["user_id"], connector["session_id"])
    return {
        "live_scene": stream["live_scene"],
        "backup_scene": stream["backup_scene"],
        "network_probe_interval_seconds": stream["network_probe_interval_seconds"],
        "network_probe_bytes": stream["network_probe_bytes"],
        "vdo_bridge_url": _vdo_ninja(request, session)["bridge_url"] if session else None,
    }
