"""Tenant-scoped session aggregation."""

from __future__ import annotations

from typing import Any

from .database import Database
from .telemetry import telemetry_snapshot


def prediction_view(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not record:
        return None
    result = record.get("result") or {}
    return {
        "status": record.get("status"),
        "model_role": record.get("model_role"),
        "model_version": record.get("model_version"),
        "probability_downgrade_needed": result.get("probability_downgrade_needed"),
        "recommendation": result.get("decision") or result.get("prediction"),
        "reason": record.get("blocked_reason"),
        "created_at": record.get("created_at"),
    }


class SessionStore:
    def __init__(self, database: Database, registry: Any) -> None:
        self.database = database
        self.registry = registry

    def detail(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        session = self.database.get_session(user_id, session_id)
        if not session:
            return None
        raw_telemetry = self.database.latest_telemetry(user_id, session_id)
        predictions = self.database.recent_predictions(user_id, session_id)
        session["telemetry"] = telemetry_snapshot(raw_telemetry, self.registry)
        session["latest_prediction"] = prediction_view(predictions[0] if predictions else None)
        session["recent_predictions"] = [prediction_view(item) for item in predictions]
        return session
