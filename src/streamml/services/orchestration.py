"""Closed-loop inference and autonomous action orchestration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.streamml.agent import AgentInput, AgentState, AutonomousStreamingAgent
from src.streamml.domain.contracts import INSUFFICIENT_DATA
from src.streamml.features.validation import IncompatibleFeatures


def process_telemetry(
    *,
    database: Any,
    engine: Any,
    registry: Any,
    agent: AutonomousStreamingAgent,
    user_id: str,
    session_id: str,
    connector_id: str,
    observed_at: str,
    metrics: dict[str, Any],
    network: dict[str, Any] | None,
) -> dict[str, Any]:
    """Run every compatible model, update agent state and queue required action."""

    predictions: list[dict[str, Any]] = []
    reactive_result: dict[str, Any] | None = None
    predictive_result: dict[str, Any] | None = None

    if network is not None:
        source = str(network["source"])
        reactive_input = [
            {"name": "upload_mbps", "value": network["upload_mbps"], "unit": "Mbps", "source": source},
            {"name": "download_mbps", "value": network["download_mbps"], "unit": "Mbps", "source": source},
            {"name": "latency_ms", "value": network["latency_ms"], "unit": "ms", "source": source},
        ]
        reactive_result = engine.predict_reactive(reactive_input)
        predictions.append(
            database.store_prediction(
                user_id=user_id,
                session_id=session_id,
                model_role="reactive",
                model_version=registry.version,
                status="executed",
                result=reactive_result,
                blocked_reason=None,
                input_fingerprint=engine.fingerprint(reactive_input),
            )
        )
    else:
        predictions.append(
            _blocked(database, registry, user_id, session_id, "reactive")
        )

    state = AgentState.from_dict(database.load_agent_state(user_id, session_id))
    required_count = int(registry.contracts["predictive"]["lookback_seconds"])
    history = database.recent_network_telemetry(user_id, session_id, required_count)
    history_is_continuous = _continuous_one_hz_window(history, required_count)
    if history_is_continuous:
        first_timestamp = _timestamp(history[0]["observed_at"])
        samples = [
            {
                "elapsed_seconds": round(_timestamp(row["observed_at"]) - first_timestamp),
                "throughput_mbps": row["network"]["connection_capacity_mbps"],
                "unit": "Mbps",
                "source": "connection_capacity_mbps",
            }
            for index, row in enumerate(history)
        ]
        try:
            predictive_result = engine.predict_predictive(
                samples, _profile_level(state.current_profile)
            )
        except IncompatibleFeatures:
            predictive_result = None
        if predictive_result is not None:
            predictions.append(
                database.store_prediction(
                    user_id=user_id,
                    session_id=session_id,
                    model_role="predictive",
                    model_version=registry.version,
                    status="executed",
                    result=predictive_result,
                    blocked_reason=None,
                    input_fingerprint=engine.fingerprint(
                        {"samples": samples, "current_profile": _profile_level(state.current_profile)}
                    ),
                )
            )
        else:
            predictions.append(
                _blocked(database, registry, user_id, session_id, "predictive")
            )
    else:
        predictions.append(
            _blocked(database, registry, user_id, session_id, "predictive")
        )

    signal_available = bool(metrics.get("obs_connected")) and bool(metrics.get("stream_active"))
    decision = agent.decide(
        state,
        AgentInput(
            observed_at=_timestamp(observed_at),
            signal_available=signal_available,
            reactive_profile=(reactive_result or {}).get("prediction"),
            predictive_decision=(predictive_result or {}).get("decision"),
            downgrade_probability=(predictive_result or {}).get("probability_downgrade_needed"),
            capacity_mbps=(network or {}).get("connection_capacity_mbps"),
        ),
    )
    decision_payload = decision.to_dict()
    database.save_agent_state(user_id, session_id, state.to_dict(), decision_payload)

    command = None
    if decision.apply_profile:
        command = database.enqueue_control_command(
            user_id=user_id,
            session_id=session_id,
            connector_id=connector_id,
            command_type="set_profile",
            payload={
                "profile": decision.target_profile,
                "previous_profile": decision.current_profile,
                "spec": decision_payload["target_profile_spec"],
                "reason": decision.reason,
            },
        )
    elif decision.apply_backup:
        command = database.enqueue_control_command(
            user_id=user_id,
            session_id=session_id,
            connector_id=connector_id,
            command_type=(
                "activate_backup" if decision.action == "switch_to_backup" else "restore_live"
            ),
            payload={
                "reason": decision.reason,
                "previous_backup_active": not decision.backup_active,
            },
        )

    return {
        "predictions": predictions,
        "decision": decision_payload,
        "command": command,
        "current_profile": state.current_profile,
    }


def _continuous_one_hz_window(history: list[dict[str, Any]], required_count: int) -> bool:
    """Reject stale, reordered or gapped telemetry instead of inventing samples."""

    if len(history) != required_count:
        return False
    try:
        timestamps = [_timestamp(row["observed_at"]) for row in history]
    except (KeyError, TypeError, ValueError):
        return False
    deltas = [later - earlier for earlier, later in zip(timestamps, timestamps[1:])]
    if any(delta <= 0 or delta > 2.0 for delta in deltas):
        return False
    expected_span = required_count - 1
    return abs((timestamps[-1] - timestamps[0]) - expected_span) <= 2.0


def _blocked(
    database: Any, registry: Any, user_id: str, session_id: str, role: str
) -> dict[str, Any]:
    return database.store_prediction(
        user_id=user_id,
        session_id=session_id,
        model_role=role,
        model_version=registry.version,
        status="blocked",
        result=None,
        blocked_reason=INSUFFICIENT_DATA,
        input_fingerprint=None,
    )


def _timestamp(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _profile_level(profile: str) -> int:
    return {"low": 1, "medium": 2, "high": 3}[profile]
