"""Endpoints estrictos de predicción con modelos oficiales."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from apps.api.dependencies import current_user, require_owned_session
from apps.api.schemas import PredictivePredictionRequest, ReactivePredictionRequest
from src.streamml.domain.contracts import INSUFFICIENT_DATA
from src.streamml.features.validation import IncompatibleFeatures
from src.streamml.services.session_store import prediction_view


router = APIRouter(prefix="/api/v1/predict", tags=["predictions"])


async def _blocked(
    request: Request, user: dict, session_id: str, role: str, details: list[str], fingerprint: str
) -> JSONResponse:
    record = request.app.state.database.store_prediction(
        user_id=user["id"],
        session_id=session_id,
        model_role=role,
        model_version=request.app.state.registry.version,
        status="blocked",
        result=None,
        blocked_reason=INSUFFICIENT_DATA,
        input_fingerprint=fingerprint,
    )
    await request.app.state.websocket_hub.publish(
        session_id,
        {
            "type": "prediction",
            "session_id": session_id,
            "prediction": prediction_view(record, request.app.state.registry),
        },
    )
    return JSONResponse(status_code=422, content={"message": INSUFFICIENT_DATA, "details": details})


async def _executed(request: Request, user: dict, session_id: str, role: str, result: dict, fingerprint: str) -> dict:
    record = request.app.state.database.store_prediction(
        user_id=user["id"],
        session_id=session_id,
        model_role=role,
        model_version=request.app.state.registry.version,
        status="executed",
        result=result,
        blocked_reason=None,
        input_fingerprint=fingerprint,
    )
    await request.app.state.websocket_hub.publish(
        session_id,
        {
            "type": "prediction",
            "session_id": session_id,
            "prediction": prediction_view(record, request.app.state.registry),
        },
    )
    return record


@router.post("/reactive")
async def predict_reactive(payload: ReactivePredictionRequest, request: Request, user: dict = Depends(current_user)):
    require_owned_session(request, user, payload.session_id)
    raw_features = [feature.model_dump(mode="python") for feature in payload.features]
    fingerprint = request.app.state.engine.fingerprint(raw_features)
    try:
        result = request.app.state.engine.predict_reactive(raw_features)
    except IncompatibleFeatures as exc:
        return await _blocked(request, user, payload.session_id, "reactive", exc.details, fingerprint)
    return await _executed(request, user, payload.session_id, "reactive", result, fingerprint)


@router.post("/predictive")
async def predict_predictive(
    payload: PredictivePredictionRequest, request: Request, user: dict = Depends(current_user)
):
    require_owned_session(request, user, payload.session_id)
    samples = [sample.model_dump(mode="python") for sample in payload.samples]
    fingerprint = request.app.state.engine.fingerprint({"samples": samples, "current_profile": payload.current_profile})
    try:
        result = request.app.state.engine.predict_predictive(samples, payload.current_profile)
    except IncompatibleFeatures as exc:
        return await _blocked(request, user, payload.session_id, "predictive", exc.details, fingerprint)
    return await _executed(request, user, payload.session_id, "predictive", result, fingerprint)
