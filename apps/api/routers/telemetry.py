"""Authenticated OBS connector telemetry ingestion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from apps.api.dependencies import client_ip, current_connector, current_user, require_owned_session
from apps.api.schemas import TelemetryRequest, VdoNinjaTelemetryRequest
from apps.api.routers.sessions import _vdo_ninja
from src.streamml.services.orchestration import process_telemetry
from src.streamml.services.telemetry import (
    feature_availability,
    merge_vdo_network,
    telemetry_snapshot,
    vdo_phone_status,
)
from src.streamml.services.session_store import prediction_view
from src.streamml.security.vdo import valid_vdo_bridge_token


router = APIRouter(prefix="/api/v1", tags=["telemetry"])


def _authorized_vdo_session(request: Request, session_id: str) -> tuple[dict, dict]:
    """Authorize either the signed-in GUI or the OBS bridge's scoped bearer token."""

    try:
        user = current_user(request)
    except HTTPException:
        authorization = request.headers.get("authorization", "")
        scheme, _, supplied = authorization.partition(" ")
        if scheme.lower() != "bearer" or not valid_vdo_bridge_token(
            request.app.state.settings.media_auth_secret, session_id, supplied
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="VDO.Ninja telemetry authentication required.",
            )
        session = request.app.state.database.get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
        return {"id": session["user_id"]}, session
    session = require_owned_session(request, user, session_id)
    return user, session


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
    connector_network = payload.network.model_dump(mode="json") if payload.network else None
    phone = request.app.state.database.latest_vdo_telemetry(connector["user_id"], connector["session_id"])
    phone_status = vdo_phone_status(phone, payload.observed_at)
    network = merge_vdo_network(connector_network, phone, payload.observed_at)
    unsupported = payload.unsupported.model_dump(mode="json")
    record, inserted = request.app.state.database.store_telemetry(
        user_id=connector["user_id"],
        session_id=connector["session_id"],
        connector_id=connector["id"],
        sequence=payload.sequence,
        observed_at=payload.observed_at,
        source=payload.source,
        metrics=metrics,
        network=network,
        unsupported=unsupported,
    )
    result = None
    if inserted:
        session_status = (
            "active" if metrics.get("stream_active") else "ready" if metrics.get("obs_connected") else "offline"
        )
        request.app.state.database.update_session_status(connector["user_id"], connector["session_id"], session_status)
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
            phone_signal_available=(
                False
                if phone is not None and phone_status != "connected"
                else True
                if phone_status == "connected"
                else None
            ),
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
        "telemetry": telemetry_snapshot(record, request.app.state.registry, phone),
        "availability": availability,
        "predictions": [prediction_view(item, request.app.state.registry) for item in predictions],
        "prediction": prediction_view(predictions[-1], request.app.state.registry) if predictions else None,
        "agent_decision": result["decision"] if result else None,
        "control_command": result["command"] if result else None,
    }
    if inserted:
        await request.app.state.websocket_hub.publish(connector["session_id"], event)
    request.app.state.database.record_audit(
        user_id=connector["user_id"],
        actor_type="connector",
        action="telemetry.ingest",
        resource_type="session",
        resource_id=connector["session_id"],
        outcome="success" if inserted else "duplicate",
        client_ip=client_ip(request),
        details={"sequence": payload.sequence, "source": payload.source},
    )
    inference_executed = any(item.get("status") == "executed" for item in predictions)
    return {
        "accepted": True,
        "duplicate": not inserted,
        "telemetry_id": record["id"],
        "session_id": connector["session_id"],
        "availability": availability,
        "inference": {
            "status": "executed" if inference_executed else "blocked",
            "message": None if inference_executed else "Datos insuficientes para una predicción válida",
            "predictions": [prediction_view(item, request.app.state.registry) for item in predictions],
        },
        "agent_decision": result["decision"] if result else None,
        "control_command": result["command"] if result else None,
    }


@router.post("/telemetry/vdo-ninja")
async def receive_vdo_ninja_telemetry(
    payload: VdoNinjaTelemetryRequest,
    request: Request,
) -> dict:
    """Receive only normalized WebRTC data from the authenticated monitoring GUI."""

    user, _session = _authorized_vdo_session(request, payload.session_id)
    settings = request.app.state.settings
    rate_key = f"vdo-telemetry:{user['id']}:{payload.session_id}:{payload.reporter_id}"
    if not request.app.state.rate_limiter.allow(rate_key, settings.telemetry_limit, settings.rate_window_seconds):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many telemetry events.")
    _record, inserted = request.app.state.database.store_vdo_telemetry(
        user_id=user["id"],
        session_id=payload.session_id,
        reporter_id=payload.reporter_id,
        sequence=payload.sequence,
        observed_at=payload.observed_at,
        status=payload.status,
        metrics=payload.metrics.model_dump(mode="json", exclude_none=True),
    )
    phone_view = request.app.state.database.latest_vdo_telemetry(user["id"], payload.session_id)
    raw_telemetry = request.app.state.database.latest_telemetry(user["id"], payload.session_id)
    if raw_telemetry:
        network_view = dict(raw_telemetry.get("network") or {})
        agent_state = request.app.state.database.load_agent_state(user["id"], payload.session_id)
        if agent_state and agent_state.get("current_profile"):
            network_view["current_profile"] = agent_state["current_profile"]
        raw_telemetry["network"] = network_view or None
    snapshot = telemetry_snapshot(
        raw_telemetry,
        request.app.state.registry,
        phone_view,
        reference_at=payload.observed_at,
    )
    if inserted:
        await request.app.state.websocket_hub.publish(
            payload.session_id,
            {
                "type": "vdo_telemetry",
                "session_id": payload.session_id,
                "telemetry": snapshot,
            },
        )
    return {
        "accepted": True,
        "duplicate": not inserted,
        "phone_status": vdo_phone_status(phone_view, payload.observed_at),
    }


@router.get("/telemetry/vdo-ninja/{session_id}/bridge")
def vdo_ninja_bridge_configuration(session_id: str, request: Request) -> dict:
    _user, session = _authorized_vdo_session(request, session_id)
    return {"session_id": session_id, "embed_url": _vdo_ninja(request, session)["embed_url"]}
