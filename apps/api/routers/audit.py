"""Endpoints para la consulta de logs y auditoría."""

from fastapi import APIRouter, Depends, Query, Request
from src.streamml.services.database import Database
from apps.api.dependencies import current_user

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

@router.get("/events")
def list_audit_events(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    level: str | None = Query(None, description="Filtro de severidad: error, warning, success, info"),
    action: str | None = Query(None, description="Filtro parcial por tipo de acción"),
    user: dict = Depends(current_user),
):
    database: Database = request.app.state.database
    events, total = database.list_audit_events(
        user_id=user["id"],
        limit=limit,
        offset=offset,
        level=level,
        action=action,
    )
    return {
        "items": events,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
