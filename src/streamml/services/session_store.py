"""Agregación de sesiones con alcance por tenant."""

from __future__ import annotations

from typing import Any

from src.streamml.security.auth import utc_now_iso

from .database import Database
from .telemetry import telemetry_snapshot


def prediction_view(record: dict[str, Any] | None, registry: Any | None = None) -> dict[str, Any] | None:
    if not record:
        return None
    result = record.get("result") or {}
    stored_status = record.get("status")
    view = {
        "status": stored_status,
        "model_role": record.get("model_role"),
        "model_version": record.get("model_version"),
        "probability_downgrade_needed": result.get("probability_downgrade_needed"),
        "recommendation": result.get("decision") or result.get("prediction"),
        "reason": result.get("explanation") or record.get("blocked_reason"),
        "evidence": result.get("evidence"),
        "created_at": record.get("created_at"),
    }
    role = record.get("model_role")
    if registry is not None and role in registry.contracts:
        contract = registry.contracts[role]
        available = stored_status in {"available", "executed"}
        view["features"] = [
            {
                "name": name,
                "state": "available" if available else "missing",
                "unit": contract.get("feature_metadata", {}).get(name, {}).get("unit"),
                "reason": (
                    "Variable validada y utilizada por la inferencia oficial."
                    if available
                    else record.get("blocked_reason") or "La variable todavía no cumple el contrato del modelo."
                ),
            }
            for name in contract["features"]
        ]
    return view


class SessionStore:
    def __init__(self, database: Database, registry: Any) -> None:
        self.database = database
        self.registry = registry

    def detail(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        session = self.database.get_session(user_id, session_id)
        if not session:
            return None
        raw_telemetry = self.database.latest_telemetry(user_id, session_id)
        phone_telemetry = self.database.latest_vdo_telemetry(user_id, session_id)
        predictions = self.database.recent_predictions(user_id, session_id)
        agent_state = self.database.load_agent_state(user_id, session_id)
        if raw_telemetry and raw_telemetry.get("network") and agent_state:
            raw_telemetry["network"]["current_profile"] = agent_state.get("current_profile")
        session["telemetry"] = telemetry_snapshot(
            raw_telemetry, self.registry, phone_telemetry, reference_at=utc_now_iso()
        )
        session["latest_prediction"] = prediction_view(predictions[0] if predictions else None, self.registry)
        session["recent_predictions"] = [prediction_view(item, self.registry) for item in predictions]
        session["agent_decision"] = self.database.latest_agent_decision(user_id, session_id)
        return session
