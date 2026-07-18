from src.streamml.evaluation.control_replay import (
    ReplaySample,
    demonstration_samples,
    replay_control_strategies,
)


def test_replay_compares_all_strategies_without_claiming_physical_qoe() -> None:
    report = replay_control_strategies(demonstration_samples())
    assert set(report["strategies"]) == {
        "fixed_profile",
        "reactive_only",
        "reactive_predictive_agent",
    }
    assert "not a substitute" in report["metric"]["warning"]
    assert report["strategies"]["reactive_predictive_agent"]["backup_seconds"] > 0
    assert report["full_agent_improvement_over_fixed_points"] > 0


def test_replay_rejects_non_positive_durations() -> None:
    sample = ReplaySample(0, 0, True, 10, "high", "maintain", 0.1)
    try:
        replay_control_strategies([sample])
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("Replay accepted a non-positive duration.")
