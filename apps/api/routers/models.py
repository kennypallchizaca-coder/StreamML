"""Read-only official model catalogue."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from apps.api.dependencies import current_user


router = APIRouter(prefix="/api/v1", tags=["models"])


@router.get("/models")
def list_models(request: Request, _user: dict = Depends(current_user)) -> dict:
    return {
        "release_version": request.app.state.registry.version,
        "operational_status": "verified",
        "production_ready": request.app.state.settings.production_controls_ready(),
        "models": request.app.state.registry.public_models(),
    }
