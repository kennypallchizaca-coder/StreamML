"""Deterministic controller replay and transparent QoE-proxy comparison."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.streamml.agent.policy import (
    PROFILE_SPECS,
    AgentInput,
    AgentState,
    AutonomousStreamingAgent,
    ProfileName,
)


@dataclass(frozen=True, slots=True)
class ReplaySample:
    observed_at: float
    duration_seconds: float
    signal_available: bool
    capacity_mbps: float
    reactive_profile: ProfileName | None
    predictive_decision: Literal["maintain", "downgrade_needed"] | None
    downgrade_probability: float | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ReplaySample":
        return cls(
            observed_at=float(value["observed_at"]),
            duration_seconds=float(value.get("duration_seconds", 1.0)),
            signal_available=bool(value["signal_available"]),
            capacity_mbps=float(value["capacity_mbps"]),
            reactive_profile=value.get("reactive_profile"),
            predictive_decision=value.get("predictive_decision"),
            downgrade_probability=(
                None
                if value.get("downgrade_probability") is None
                else float(value["downgrade_probability"])
            ),
        )


def _safe_profile(capacity_mbps: float, margin: float = 0.85) -> ProfileName:
    usable = max(0.0, capacity_mbps) * margin
    safe: ProfileName = "low"
    for name, spec in PROFILE_SPECS.items():
        if spec.required_capacity_mbps <= usable and spec.level > PROFILE_SPECS[safe].level:
            safe = name
    return safe


def _lower_profile(left: ProfileName, right: ProfileName) -> ProfileName:
    return left if PROFILE_SPECS[left].level <= PROFILE_SPECS[right].level else right


def _score_strategy(
    samples: list[ReplaySample],
    profiles: list[ProfileName],
    backup_active: list[bool],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    total = sum(sample.duration_seconds for sample in samples)
    content_seconds = 0.0
    unsupported_seconds = 0.0
    backup_seconds = 0.0
    weighted_quality = 0.0
    live_seconds = 0.0
    live_level_sum = 0.0
    for sample, profile, backup in zip(samples, profiles, backup_active, strict=True):
        required = PROFILE_SPECS[profile].required_capacity_mbps
        supported = sample.signal_available and sample.capacity_mbps * 0.85 >= required
        if backup:
            backup_seconds += sample.duration_seconds
            content_seconds += sample.duration_seconds
            weighted_quality += 0.25 * sample.duration_seconds
        elif supported:
            content_seconds += sample.duration_seconds
            quality = PROFILE_SPECS[profile].level / 3.0
            weighted_quality += quality * sample.duration_seconds
            live_seconds += sample.duration_seconds
            live_level_sum += PROFILE_SPECS[profile].level * sample.duration_seconds
        else:
            unsupported_seconds += sample.duration_seconds
    switches = sum(left != right for left, right in zip(profiles, profiles[1:]))
    interruptions = max(0.0, total - content_seconds)
    continuity = content_seconds / total if total else 0.0
    quality = weighted_quality / total if total else 0.0
    allowed_switches = max(1.0, total / 30.0)
    stability = 1.0 - min(1.0, switches / allowed_switches)
    # StreamML's declared objective is continuity first: avoiding a frozen or
    # absent output matters more than briefly operating at a lower profile.
    score = 100.0 * (0.90 * continuity + 0.05 * quality + 0.05 * stability)
    return {
        "duration_seconds": total,
        "content_available_seconds": content_seconds,
        "interruption_seconds": interruptions,
        "unsupported_profile_seconds": unsupported_seconds,
        "backup_seconds": backup_seconds,
        "profile_switches": switches,
        "average_live_profile_level": live_level_sum / live_seconds if live_seconds else 0.0,
        "continuity_ratio": continuity,
        "quality_ratio": quality,
        "stability_ratio": stability,
        "qoe_proxy_score": score,
        "events": events,
    }


def replay_control_strategies(
    samples: list[ReplaySample], initial_profile: ProfileName = "high"
) -> dict[str, Any]:
    if not samples:
        raise ValueError("At least one replay sample is required.")
    if any(sample.duration_seconds <= 0 for sample in samples):
        raise ValueError("Replay durations must be positive.")

    fixed_profiles = [initial_profile] * len(samples)
    fixed_backup = [False] * len(samples)

    reactive_profiles: list[ProfileName] = []
    reactive_events: list[dict[str, Any]] = []
    reactive_current = initial_profile
    for sample in samples:
        recommended = sample.reactive_profile or reactive_current
        next_profile = _lower_profile(recommended, _safe_profile(sample.capacity_mbps))
        if next_profile != reactive_current:
            reactive_events.append({
                "observed_at": sample.observed_at,
                "action": "set_profile",
                "from": reactive_current,
                "to": next_profile,
                "reason": "reactive_recommendation",
            })
        reactive_current = next_profile
        reactive_profiles.append(reactive_current)

    agent = AutonomousStreamingAgent()
    state = AgentState(current_profile=initial_profile)
    agent_profiles: list[ProfileName] = []
    agent_backup: list[bool] = []
    agent_events: list[dict[str, Any]] = []
    for sample in samples:
        decision = agent.decide(
            state,
            AgentInput(
                observed_at=sample.observed_at,
                signal_available=sample.signal_available,
                reactive_profile=sample.reactive_profile,
                predictive_decision=sample.predictive_decision,
                downgrade_probability=sample.downgrade_probability,
                capacity_mbps=sample.capacity_mbps,
            ),
        )
        agent_profiles.append(state.current_profile)
        agent_backup.append(state.backup_active)
        if decision.action != "maintain" or decision.apply_profile or decision.apply_backup:
            agent_events.append({
                "observed_at": sample.observed_at,
                "action": decision.action,
                "from": decision.current_profile,
                "to": decision.target_profile,
                "backup_active": decision.backup_active,
                "reason": decision.reason,
                "reason_code": decision.reason_code,
                "operational_state": decision.operational_state,
            })

    strategies = {
        "fixed_profile": _score_strategy(samples, fixed_profiles, fixed_backup, []),
        "reactive_only": _score_strategy(
            samples, reactive_profiles, [False] * len(samples), reactive_events
        ),
        "reactive_predictive_agent": _score_strategy(
            samples, agent_profiles, agent_backup, agent_events
        ),
    }
    baseline = strategies["fixed_profile"]["qoe_proxy_score"]
    full = strategies["reactive_predictive_agent"]["qoe_proxy_score"]
    return {
        "metric": {
            "name": "StreamML continuity-first QoE proxy",
            "version": "1.0.0",
            "formula": "100 * (0.90 continuity + 0.05 normalized quality + 0.05 stability)",
            "warning": "This engineering proxy validates controller behavior; it is not a substitute for physical QoE measurements.",
        },
        "strategies": strategies,
        "full_agent_improvement_over_fixed_points": full - baseline,
    }


def demonstration_samples() -> list[ReplaySample]:
    """A declared synthetic scenario for repeatable policy testing only."""

    samples: list[ReplaySample] = []
    for second in range(150):
        if second < 40:
            capacity, reactive, predictive, probability, signal = 9.0, "high", "maintain", 0.08, True
        elif second < 50:
            capacity, reactive, predictive, probability, signal = 7.0, "high", "maintain", 0.32, True
        elif second < 60:
            capacity, reactive, predictive, probability, signal = 5.5, "medium", "downgrade_needed", 0.78, True
        elif second < 80:
            capacity, reactive, predictive, probability, signal = 3.0, "low", "downgrade_needed", 0.91, True
        elif second < 85:
            capacity, reactive, predictive, probability, signal = 0.0, None, None, None, False
        elif second < 105:
            capacity, reactive, predictive, probability, signal = 4.2, "medium", "maintain", 0.19, True
        else:
            capacity, reactive, predictive, probability, signal = 9.0, "high", "maintain", 0.06, True
        samples.append(ReplaySample(
            observed_at=float(second),
            duration_seconds=1.0,
            signal_available=signal,
            capacity_mbps=capacity,
            reactive_profile=reactive,
            predictive_decision=predictive,
            downgrade_probability=probability,
        ))
    return samples
