from datetime import datetime, timezone

from intelligence.event_calendar import build_event_calendar


def test_event_calendar_filters_stale_events(now: datetime) -> None:
    result = build_event_calendar(
        [{"event_id": "old", "event_type": "unlock", "scheduled_at": "2026-05-01T00:00:00+00:00"}],
        now=now,
    )

    assert result.status == "INSUFFICIENT_DATA"
    assert "CALENDAR_EVENTS_STALE" in result.reason_codes


def test_event_calendar_accepts_fresh_fixture(now: datetime) -> None:
    result = build_event_calendar(
        [
            {
                "event_id": "unlock-1",
                "subject_id": "fixture-sol-usdc",
                "event_type": "token_unlock",
                "scheduled_at": "2026-05-23T12:00:00+00:00",
                "impact": "high",
            }
        ],
        now=now,
    )

    assert result.status == "OK"
    assert result.events[0].scheduled_at.tzinfo is not None
    assert result.to_dict()["can_execute_trades"] is False

