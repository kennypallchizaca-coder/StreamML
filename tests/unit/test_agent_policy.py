from src.streamml.agent import (
    AgentInput,
    AgentPolicy,
    AgentState,
    AutonomousStreamingAgent,
)


def test_predictive_risk_reduces_before_reactive_failure() -> None:
    agent = AutonomousStreamingAgent()
    state = AgentState(current_profile="high")
    decision = agent.decide(
        state,
        AgentInput(
            observed_at=100,
            signal_available=True,
            reactive_profile="high",
            predictive_decision="downgrade_needed",
            downgrade_probability=0.80,
            capacity_mbps=10,
        ),
    )
    assert decision.action == "reduce"
    assert decision.target_profile == "medium"
    assert decision.apply_profile is True
    assert state.current_profile == "medium"


def test_safety_margin_caps_reactive_recommendation() -> None:
    agent = AutonomousStreamingAgent(AgentPolicy(capacity_safety_margin=0.80))
    state = AgentState(current_profile="high")
    decision = agent.decide(
        state,
        AgentInput(
            observed_at=100,
            signal_available=True,
            reactive_profile="high",
            predictive_decision="maintain",
            capacity_mbps=5,
        ),
    )
    assert decision.action == "reduce"
    assert decision.target_profile == "medium"


def test_upgrade_requires_hysteresis_and_respects_one_level() -> None:
    agent = AutonomousStreamingAgent(
        AgentPolicy(upgrade_confirmations=3, minimum_change_interval_seconds=0)
    )
    state = AgentState(current_profile="low")
    for second in (1, 2):
        decision = agent.decide(
            state,
            AgentInput(
                observed_at=second,
                signal_available=True,
                reactive_profile="high",
                predictive_decision="maintain",
                capacity_mbps=20,
            ),
        )
        assert decision.action == "maintain"
    decision = agent.decide(
        state,
        AgentInput(
            observed_at=3,
            signal_available=True,
            reactive_profile="high",
            predictive_decision="maintain",
            capacity_mbps=20,
        ),
    )
    assert decision.action == "increase"
    assert decision.target_profile == "medium"


def test_upgrade_cooldown_resets_confirmation_streak() -> None:
    agent = AutonomousStreamingAgent(
        AgentPolicy(upgrade_confirmations=2, minimum_change_interval_seconds=30)
    )
    state = AgentState(current_profile="medium", last_profile_change_at=90)
    decision = agent.decide(
        state,
        AgentInput(100, True, "high", "maintain", 0.1, 20),
    )
    assert decision.action == "maintain"
    assert state.upgrade_streak == 0


def test_signal_loss_backup_and_stable_recovery() -> None:
    agent = AutonomousStreamingAgent(
        AgentPolicy(signal_loss_grace_seconds=3, recovery_stable_seconds=10)
    )
    state = AgentState()
    assert agent.decide(state, AgentInput(0, False)).action == "maintain"
    switched = agent.decide(state, AgentInput(3, False))
    assert switched.action == "switch_to_backup"
    assert switched.apply_backup is True
    assert state.backup_active is True
    assert agent.decide(state, AgentInput(20, True)).action == "maintain_backup"
    restored = agent.decide(state, AgentInput(30, True))
    assert restored.action == "restore_live"
    assert restored.apply_backup is True
    assert state.backup_active is False


def test_state_roundtrip() -> None:
    state = AgentState(
        current_profile="high", backup_active=True, last_profile_change_at=1.5,
        signal_lost_at=2.0, signal_recovered_at=3.0, upgrade_streak=4,
    )
    assert AgentState.from_dict(state.to_dict()) == state
