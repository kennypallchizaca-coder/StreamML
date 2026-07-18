from datetime import datetime, timedelta, timezone

from src.streamml.services.orchestration import _continuous_one_hz_window, _predictive_samples


def _history(offsets: list[float]) -> list[dict]:
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "observed_at": (origin + timedelta(seconds=value)).isoformat(),
            "network": {"connection_capacity_mbps": 5.0 + value},
        }
        for value in offsets
    ]


def test_predictive_history_requires_a_complete_continuous_one_hz_window() -> None:
    assert _continuous_one_hz_window(_history([0, 1, 2, 3]), 4)
    assert _continuous_one_hz_window(_history([0, 1.1, 2.2, 3.3]), 4)
    assert not _continuous_one_hz_window(_history([0, 1, 4, 5]), 4)
    assert not _continuous_one_hz_window(_history([0, 1, 2]), 4)
    assert not _continuous_one_hz_window(_history([0, 1, 1, 3]), 4)


def test_predictive_history_resamples_real_jittered_measurements_to_one_hz() -> None:
    samples = _predictive_samples(_history([0, 1.1, 2.2, 3.3, 4.4]), 4)
    assert samples is not None
    assert [sample["elapsed_seconds"] for sample in samples] == [0, 1, 2, 3]
    assert all(sample["source"] == "connection_capacity_mbps" for sample in samples)


def test_predictive_history_ignores_gaps_older_than_the_required_window() -> None:
    samples = _predictive_samples(_history([0, 100, 101, 102, 103]), 4)
    assert samples is not None
