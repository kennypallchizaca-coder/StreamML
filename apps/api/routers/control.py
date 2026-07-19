"""Authenticated command delivery and acknowledgement for local connectors."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from apps.api.dependencies import current_connector
from apps.api.schemas import ControlCommandAck


router = APIRouter(prefix="/api/v1/connectors/commands", tags=["connector-control"])


@router.get("/next")
def next_command(request: Request, connector: dict = Depends(current_connector)) -> dict:
    command = request.app.state.database.pending_control_command(connector["id"], connector["session_id"])
    if not command:
        return {"command": None}
    return {
        "command": {
            "id": command["id"],
            "command_type": command["command_type"],
            "payload": command["payload"],
            "created_at": command["created_at"],
        }
    }


@router.post("/{command_id}/ack")
def acknowledge_command(
    command_id: str,
    payload: ControlCommandAck,
    request: Request,
    connector: dict = Depends(current_connector),
) -> dict:
    updated = request.app.state.database.acknowledge_control_command(
        connector["id"],
        command_id,
        success=payload.success,
        error_message=payload.error_message,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found.")
    request.app.state.database.record_audit(
        user_id=connector["user_id"],
        actor_type="connector",
        action="control.command.acknowledge",
        resource_type="control_command",
        resource_id=command_id,
        outcome="success" if payload.success else "failed",
        details={"error_type": payload.error_message if not payload.success else None},
    )
    return {"acknowledged": True, "status": "completed" if payload.success else "failed"}
