"""Authenticated OBS connector telemetry ingestion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from apps.api.dependencies import client_ip, current_connector
from apps.api.schemas import TelemetryRequest
from src.streamml.domain.contracts import INSUFFICIENT_DATA
from src.streamml.services.telemetry import feature_availability, telemetry_snapshot
from src.streamml.services.session_store import prediction_view


router = APIRouter(prefix="/api/v1", tags=["telemetry"])


@router.post("/telemetry")
async def receive_telemetry(
    payload: TelemetryRequest, request: Request, connector: dict = Depends(current_connector)
) -> dict:
    settings = request.app.state.settings
    if payload.session_id != connector["session_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    if not request.app.state.rate_limiter.allow(
        f"telemetry:{connector['id']}", settings.telemetry_limit, settings.rate_window_seconds
    ):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many telemetry events.")
    metrics = payload.metrics.model_dump(mode="json")
    unsupported = payload.unsupported.model_dump(mode="json")
    record, inserted = request.app.state.database.store_telemetry(
        user_id=connector["user_id"], session_id=connector["session_id"], connector_id=connector["id"],
        sequence=payload.sequence, observed_at=payload.observed_at, source=payload.source,
        metrics=metrics, unsupported=unsupported,
    )
    availability = feature_availability(metrics)
    blocked_predictions = []
    if inserted:
        for role in ("reactive", "predictive"):
            blocked = request.app.state.database.store_prediction(
                user_id=connector["user_id"], session_id=connector["session_id"], model_role=role,
                model_version=request.app.state.registry.version, status="blocked", result=None,
                blocked_reason=INSUFFICIENT_DATA, input_fingerprint=None,
            )
            blocked_predictions.append(blocked)
    event = {
        "type": "telemetry",
        "session_id": connector["session_id"],
        "telemetry": telemetry_snapshot(record, request.app.state.registry),
        "availability": availability,
        "predictions": blocked_predictions,
        "prediction": prediction_view(blocked_predictions[-1]) if blocked_predictions else None,
    }
    if inserted:
        await request.app.state.websocket_hub.publish(connector["session_id"], event)
    request.app.state.database.record_audit(
        user_id=connector["user_id"], actor_type="connector", action="telemetry.ingest",
        resource_type="session", resource_id=connector["session_id"],
        outcome="success" if inserted else "duplicate", client_ip=client_ip(request),
        details={"sequence": payload.sequence, "source": payload.source},
    )
    return {
        "accepted": True,
        "duplicate": not inserted,
        "telemetry_id": record["id"],
        "session_id": connector["session_id"],
        "availability": availability,
        "inference": {"status": "blocked", "message": INSUFFICIENT_DATA},
    }
