"""Authenticated OBS connector telemetry ingestion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from apps.api.dependencies import client_ip, current_connector
from apps.api.schemas import TelemetryRequest
from src.streamml.services.orchestration import process_telemetry
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
    network = payload.network.model_dump(mode="json") if payload.network else None
    unsupported = payload.unsupported.model_dump(mode="json")
    record, inserted = request.app.state.database.store_telemetry(
        user_id=connector["user_id"], session_id=connector["session_id"], connector_id=connector["id"],
        sequence=payload.sequence, observed_at=payload.observed_at, source=payload.source,
        metrics=metrics, network=network, unsupported=unsupported,
    )
    result = None
    if inserted:
        session_status = (
            "active" if metrics.get("stream_active") else
            "ready" if metrics.get("obs_connected") else
            "offline"
        )
        request.app.state.database.update_session_status(
            connector["user_id"], connector["session_id"], session_status
        )
        result = process_telemetry(
            database=request.app.state.database,
            engine=request.app.state.engine,
            registry=request.app.state.registry,
            agent=request.app.state.agent,
            user_id=connector["user_id"],
            session_id=connector["session_id"],
            connector_id=connector["id"],
            observed_at=payload.observed_at,
            metrics=metrics,
            network=network,
        )
    network_view = dict(network or {})
    if result:
        network_view["current_profile"] = result["current_profile"]
    record["network"] = network_view or None
    availability = feature_availability(metrics, network_view)
    predictions = result["predictions"] if result else []
    event = {
        "type": "telemetry",
        "session_id": connector["session_id"],
        "telemetry": telemetry_snapshot(record, request.app.state.registry),
        "availability": availability,
        "predictions": [prediction_view(item, request.app.state.registry) for item in predictions],
        "prediction": prediction_view(predictions[-1], request.app.state.registry) if predictions else None,
        "agent_decision": result["decision"] if result else None,
        "control_command": result["command"] if result else None,
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
        "inference": {
            "status": "executed" if network is not None else "blocked",
            "message": None if network is not None else "Datos insuficientes para una predicción válida",
            "predictions": [prediction_view(item, request.app.state.registry) for item in predictions],
        },
        "agent_decision": result["decision"] if result else None,
        "control_command": result["command"] if result else None,
    }
