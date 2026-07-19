"""Closed-loop inference and autonomous action orchestration."""

from __future__ import annotations

from datetime import datetime
import math
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
    phone_signal_available: bool | None = None,
) -> dict[str, Any]:
    """Run every compatible model, update agent state and queue required action."""

    predictions: list[dict[str, Any]] = []
    reactive_result: dict[str, Any] | None = None
    predictive_result: dict[str, Any] | None = None

    reactive_network_ready = network is not None and all(
        network.get(name) is not None for name in ("source", "upload_mbps", "download_mbps", "latency_ms")
    )
    if reactive_network_ready:
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
        predictions.append(_blocked(database, registry, user_id, session_id, "reactive"))

    stored_state = database.load_agent_state(user_id, session_id)
    if stored_state is None:
        configured_profile = (
            (database.get_session(user_id, session_id) or {}).get("configuration", {}).get("initial_profile")
        )
        state = AgentState(
            current_profile=configured_profile if configured_profile in {"low", "medium", "high"} else "medium"
        )
    else:
        state = AgentState.from_dict(stored_state)
    required_count = int(registry.contracts["predictive"]["lookback_seconds"])
    # The connector cadence includes request time and is therefore not exactly
    # one second. Fetch enough real observations for the fastest supported
    # cadence, then interpolate only inside a continuous measured interval.
    history = database.recent_network_telemetry(user_id, session_id, required_count * 5 + 5)
    samples = _predictive_samples(history, required_count)
    if samples is not None:
        try:
            predictive_result = engine.predict_predictive(samples, _profile_level(state.current_profile))
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
            predictions.append(_blocked(database, registry, user_id, session_id, "predictive"))
    else:
        predictions.append(_blocked(database, registry, user_id, session_id, "predictive"))

    signal_available = (
        bool(metrics.get("obs_connected"))
        and bool(metrics.get("stream_active"))
        and not bool(metrics.get("stream_reconnecting"))
        and phone_signal_available is not False
    )
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
            command_type=("activate_backup" if decision.action == "switch_to_backup" else "restore_live"),
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


def _predictive_samples(history: list[dict[str, Any]], required_count: int) -> list[dict[str, Any]] | None:
    """Resample real, continuous capacity observations to the model's 1 Hz grid."""

    if required_count < 2 or len(history) < 2:
        return None
    try:
        points = [
            (
                _timestamp(row["observed_at"]),
                float(row["network"]["connection_capacity_mbps"]),
            )
            for row in history
        ]
    except (KeyError, TypeError, ValueError):
        return None
    if any(not math.isfinite(value) or value < 0 for _, value in points):
        return None
    end_at = points[-1][0]
    start_at = end_at - (required_count - 1)
    if points[0][0] > start_at:
        return None
    coverage_start = max(index for index, point in enumerate(points[:-1]) if point[0] <= start_at)
    points = points[coverage_start:]
    deltas = [later[0] - earlier[0] for earlier, later in zip(points, points[1:])]
    if any(delta <= 0 or delta > 2.0 for delta in deltas):
        return None

    samples: list[dict[str, Any]] = []
    right = 1
    for elapsed in range(required_count):
        target = start_at + elapsed
        while right < len(points) and points[right][0] < target:
            right += 1
        if right >= len(points):
            return None
        left_point = points[right - 1]
        right_point = points[right]
        if target < left_point[0] or target > right_point[0]:
            return None
        if target == right_point[0]:
            capacity = right_point[1]
        elif target == left_point[0]:
            capacity = left_point[1]
        else:
            ratio = (target - left_point[0]) / (right_point[0] - left_point[0])
            capacity = left_point[1] + ratio * (right_point[1] - left_point[1])
        samples.append(
            {
                "elapsed_seconds": elapsed,
                "throughput_mbps": capacity,
                "unit": "Mbps",
                "source": "connection_capacity_mbps",
            }
        )
    return samples


def _continuous_one_hz_window(history: list[dict[str, Any]], required_count: int) -> bool:
    """Compatibility predicate retained for callers and focused unit tests."""

    return _predictive_samples(history, required_count) is not None


def _blocked(database: Any, registry: Any, user_id: str, session_id: str, role: str) -> dict[str, Any]:
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
