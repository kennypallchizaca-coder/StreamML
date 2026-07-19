"""Deterministic policy that turns model outputs into safe streaming actions.

The machine-learning models only recommend network profiles.  This module owns
the operational rules: safety margin, one-level changes, downgrade priority,
upgrade hysteresis, cooldowns and live/fallback switching.  Keeping those
rules outside the models makes every action explainable and straightforward to
test or audit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Literal


ProfileName = Literal["low", "medium", "high"]
ActionName = Literal[
    "maintain",
    "increase",
    "reduce",
    "switch_to_backup",
    "maintain_backup",
    "restore_live",
]


@dataclass(frozen=True, slots=True)
class ProfileSpec:
    level: int
    width: int
    height: int
    fps: int
    video_bitrate_kbps: int
    audio_bitrate_kbps: int
    required_capacity_mbps: float


PROFILE_SPECS: dict[ProfileName, ProfileSpec] = {
    "low": ProfileSpec(1, 854, 480, 24, 1_000, 96, 1.35),
    "medium": ProfileSpec(2, 1280, 720, 30, 2_500, 128, 3.375),
    "high": ProfileSpec(3, 1920, 1080, 30, 5_000, 160, 6.75),
}
LEVEL_TO_PROFILE: dict[int, ProfileName] = {spec.level: name for name, spec in PROFILE_SPECS.items()}


@dataclass(frozen=True, slots=True)
class AgentPolicy:
    """Operational controls expressed in seconds and consecutive samples."""

    capacity_safety_margin: float = 0.85
    minimum_change_interval_seconds: float = 30.0
    upgrade_confirmations: int = 5
    signal_loss_grace_seconds: float = 3.0
    recovery_stable_seconds: float = 10.0
    predictive_downgrade_threshold: float = 0.50

    def __post_init__(self) -> None:
        if not 0 < self.capacity_safety_margin <= 1:
            raise ValueError("capacity_safety_margin must be in (0, 1].")
        if self.minimum_change_interval_seconds < 0:
            raise ValueError("minimum_change_interval_seconds cannot be negative.")
        if self.upgrade_confirmations < 1:
            raise ValueError("upgrade_confirmations must be positive.")
        if self.signal_loss_grace_seconds < 0 or self.recovery_stable_seconds < 0:
            raise ValueError("Signal timing values cannot be negative.")
        if not 0 <= self.predictive_downgrade_threshold <= 1:
            raise ValueError("predictive_downgrade_threshold must be in [0, 1].")


@dataclass(slots=True)
class AgentState:
    current_profile: ProfileName = "medium"
    backup_active: bool = False
    last_profile_change_at: float | None = None
    signal_lost_at: float | None = None
    signal_recovered_at: float | None = None
    upgrade_streak: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "AgentState":
        if not value:
            return cls()
        profile = value.get("current_profile", "medium")
        if profile not in PROFILE_SPECS:
            raise ValueError("Stored agent profile is invalid.")
        return cls(
            current_profile=profile,
            backup_active=bool(value.get("backup_active", False)),
            last_profile_change_at=_optional_finite(value.get("last_profile_change_at")),
            signal_lost_at=_optional_finite(value.get("signal_lost_at")),
            signal_recovered_at=_optional_finite(value.get("signal_recovered_at")),
            upgrade_streak=max(0, int(value.get("upgrade_streak", 0))),
        )


@dataclass(frozen=True, slots=True)
class AgentInput:
    observed_at: float
    signal_available: bool
    reactive_profile: ProfileName | None = None
    predictive_decision: Literal["maintain", "downgrade_needed"] | None = None
    downgrade_probability: float | None = None
    capacity_mbps: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.observed_at)):
            raise ValueError("observed_at must be finite.")
        if self.reactive_profile is not None and self.reactive_profile not in PROFILE_SPECS:
            raise ValueError("reactive_profile is invalid.")
        if self.predictive_decision not in {None, "maintain", "downgrade_needed"}:
            raise ValueError("predictive_decision is invalid.")
        if self.downgrade_probability is not None and not 0 <= self.downgrade_probability <= 1:
            raise ValueError("downgrade_probability must be in [0, 1].")
        if self.capacity_mbps is not None and (not math.isfinite(float(self.capacity_mbps)) or self.capacity_mbps < 0):
            raise ValueError("capacity_mbps must be finite and non-negative.")


@dataclass(frozen=True, slots=True)
class AgentDecision:
    action: ActionName
    current_profile: ProfileName
    target_profile: ProfileName
    backup_active: bool
    reason: str
    reason_code: str
    operational_state: Literal["stable", "observing", "protecting", "degraded", "backup", "recovering"]
    apply_profile: bool = False
    apply_backup: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["target_profile_spec"] = asdict(PROFILE_SPECS[self.target_profile])
        return value


class AutonomousStreamingAgent:
    """Stateful, deterministic controller for one streaming session."""

    def __init__(self, policy: AgentPolicy | None = None) -> None:
        self.policy = policy or AgentPolicy()

    def decide(self, state: AgentState, input_data: AgentInput) -> AgentDecision:
        now = float(input_data.observed_at)
        if not input_data.signal_available:
            return self._on_signal_loss(state, now)
        recovery = self._on_signal_available(state, now)
        if recovery is not None:
            return recovery

        current_level = PROFILE_SPECS[state.current_profile].level
        safe_reactive = self._safe_reactive_profile(input_data.reactive_profile, input_data.capacity_mbps)
        requested_level = PROFILE_SPECS[safe_reactive].level if safe_reactive else current_level
        predictive_risk = input_data.predictive_decision == "downgrade_needed" or (
            input_data.downgrade_probability is not None
            and input_data.downgrade_probability >= self.policy.predictive_downgrade_threshold
        )

        if predictive_risk or requested_level < current_level:
            state.upgrade_streak = 0
            target_level = max(1, current_level - 1)
            if requested_level < current_level:
                target_level = max(1, min(target_level, requested_level))
            if target_level == current_level:
                return self._maintain(
                    state,
                    "El perfil bajo ya es el mínimo seguro.",
                    reason_code="minimum_safe_profile",
                    operational_state="protecting",
                )
            target = LEVEL_TO_PROFILE[target_level]
            state.current_profile = target
            state.last_profile_change_at = now
            reason = (
                "Riesgo predictivo de degradación; reducción preventiva."
                if predictive_risk
                else "El modelo reactivo recomienda menor capacidad."
            )
            return AgentDecision(
                "reduce",
                LEVEL_TO_PROFILE[current_level],
                target,
                False,
                reason,
                "predictive_risk" if predictive_risk else "reactive_capacity_reduction",
                "protecting",
                apply_profile=True,
            )

        if requested_level > current_level:
            if not self._cooldown_complete(state, now):
                state.upgrade_streak = 0
                return self._maintain(
                    state,
                    "Cooldown activo antes de otro cambio de perfil.",
                    reason_code="profile_change_cooldown",
                    operational_state="observing",
                )
            if input_data.predictive_decision not in {None, "maintain"}:
                state.upgrade_streak = 0
                return self._maintain(
                    state,
                    "El modelo predictivo aún no confirma estabilidad.",
                    reason_code="predictive_stability_not_confirmed",
                    operational_state="observing",
                )
            state.upgrade_streak += 1
            if state.upgrade_streak < self.policy.upgrade_confirmations:
                return self._maintain(
                    state,
                    f"Estabilidad para aumento {state.upgrade_streak}/{self.policy.upgrade_confirmations}.",
                    reason_code="upgrade_hysteresis",
                    operational_state="observing",
                )
            target = LEVEL_TO_PROFILE[min(3, current_level + 1)]
            state.current_profile = target
            state.last_profile_change_at = now
            state.upgrade_streak = 0
            return AgentDecision(
                "increase",
                LEVEL_TO_PROFILE[current_level],
                target,
                False,
                "Estabilidad confirmada; aumento de un nivel.",
                "upgrade_stability_confirmed",
                "stable",
                apply_profile=True,
            )

        state.upgrade_streak = 0
        return self._maintain(
            state,
            "Los modelos permiten mantener el perfil actual.",
            reason_code="models_support_current_profile",
            operational_state="stable",
        )

    def _safe_reactive_profile(
        self, recommendation: ProfileName | None, capacity_mbps: float | None
    ) -> ProfileName | None:
        if recommendation is None:
            return None
        if capacity_mbps is None:
            return recommendation
        safe_capacity = capacity_mbps * self.policy.capacity_safety_margin
        safe_level = 1
        for profile, spec in PROFILE_SPECS.items():
            if spec.required_capacity_mbps <= safe_capacity:
                safe_level = max(safe_level, spec.level)
        return LEVEL_TO_PROFILE[min(PROFILE_SPECS[recommendation].level, safe_level)]

    def _on_signal_loss(self, state: AgentState, now: float) -> AgentDecision:
        state.signal_recovered_at = None
        state.upgrade_streak = 0
        if state.backup_active:
            return AgentDecision(
                "maintain_backup",
                state.current_profile,
                state.current_profile,
                True,
                "La señal principal continúa ausente; se mantiene el respaldo.",
                "backup_held_signal_absent",
                "backup",
            )
        if state.signal_lost_at is None:
            state.signal_lost_at = now
        elapsed = now - state.signal_lost_at
        if elapsed < self.policy.signal_loss_grace_seconds:
            return self._maintain(
                state,
                "Pérdida de señal dentro del margen de confirmación.",
                reason_code="signal_loss_grace_period",
                operational_state="degraded",
            )
        state.backup_active = True
        return AgentDecision(
            "switch_to_backup",
            state.current_profile,
            state.current_profile,
            True,
            "Pérdida total confirmada; activación automática del video de respaldo.",
            "signal_loss_confirmed",
            "backup",
            apply_backup=True,
        )

    def _on_signal_available(self, state: AgentState, now: float) -> AgentDecision | None:
        state.signal_lost_at = None
        if not state.backup_active:
            state.signal_recovered_at = None
            return None
        if state.signal_recovered_at is None:
            state.signal_recovered_at = now
        elapsed = now - state.signal_recovered_at
        if elapsed < self.policy.recovery_stable_seconds:
            return AgentDecision(
                "maintain_backup",
                state.current_profile,
                state.current_profile,
                True,
                "Señal recuperada; esperando estabilidad antes de restaurar el vivo.",
                "recovery_hysteresis",
                "recovering",
            )
        state.backup_active = False
        state.signal_recovered_at = None
        return AgentDecision(
            "restore_live",
            state.current_profile,
            state.current_profile,
            False,
            "Señal principal estable; restauración automática del vivo.",
            "live_signal_stable",
            "recovering",
            apply_backup=True,
        )

    def _cooldown_complete(self, state: AgentState, now: float) -> bool:
        return state.last_profile_change_at is None or (
            now - state.last_profile_change_at >= self.policy.minimum_change_interval_seconds
        )

    @staticmethod
    def _maintain(
        state: AgentState,
        reason: str,
        *,
        reason_code: str = "maintain_policy",
        operational_state: Literal["stable", "observing", "protecting", "degraded", "backup", "recovering"] = "stable",
    ) -> AgentDecision:
        return AgentDecision(
            "maintain",
            state.current_profile,
            state.current_profile,
            state.backup_active,
            reason,
            reason_code,
            operational_state,
        )


def _optional_finite(value: Any) -> float | None:
    if value is None:
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("Stored agent timestamp is invalid.")
    return parsed
