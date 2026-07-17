from datetime import datetime, timedelta, timezone

from src.streamml.services.orchestration import _continuous_one_hz_window


def _history(offsets: list[float]) -> list[dict]:
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {"observed_at": (origin + timedelta(seconds=value)).isoformat(), "network": {}}
        for value in offsets
    ]


def test_predictive_history_requires_a_complete_continuous_one_hz_window() -> None:
    assert _continuous_one_hz_window(_history([0, 1, 2, 3]), 4)
    assert not _continuous_one_hz_window(_history([0, 1, 4, 5]), 4)
    assert not _continuous_one_hz_window(_history([0, 1, 2]), 4)
    assert not _continuous_one_hz_window(_history([0, 1, 1, 3]), 4)
