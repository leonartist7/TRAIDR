from datetime import datetime, timezone

from lifecycle.models import CandidateLifecycleState, CandidateSnapshot
from lifecycle.transitions import detect_lifecycle_events


NOW = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)


def test_detects_discovered_and_disappeared() -> None:
    current = _snapshot("token-a", CandidateLifecycleState.WATCH)

    discovered = detect_lifecycle_events(previous=None, current=current, now=NOW)
    disappeared = detect_lifecycle_events(previous=current, current=None, now=NOW)

    assert discovered[0].event_type == "CANDIDATE_DISCOVERED"
    assert disappeared[0].event_type == "CANDIDATE_DISAPPEARED"
    assert disappeared[0].to_state is CandidateLifecycleState.STALE


def test_detects_opportunity_risk_liquidity_and_stale_events() -> None:
    previous = _snapshot(
        "token-a",
        CandidateLifecycleState.WATCH,
        opportunity_score=40,
        risk_score=30,
        liquidity_score=80,
        data_quality_score=90,
        appearance_count=1,
    )
    current = _snapshot(
        "token-a",
        CandidateLifecycleState.REVIEW,
        opportunity_score=55,
        risk_score=85,
        liquidity_score=55,
        data_quality_score=30,
        appearance_count=2,
    )

    events = detect_lifecycle_events(previous=previous, current=current, now=NOW)
    event_types = {event.event_type for event in events}

    assert "STATE_CHANGED" in event_types
    assert "OPPORTUNITY_IMPROVING" in event_types
    assert "RISK_INCREASING" in event_types
    assert "LIQUIDITY_DRAINING" in event_types
    assert "STALE_DATA" in event_types
    assert "REPEATED_APPEARANCE" in event_types
    assert all(event.to_dict()["can_execute_trades"] is False for event in events)


def test_detects_liquidity_improving() -> None:
    previous = _snapshot("token-a", CandidateLifecycleState.WATCH, liquidity_score=30)
    current = _snapshot("token-a", CandidateLifecycleState.ALERT, liquidity_score=50)

    events = detect_lifecycle_events(previous=previous, current=current, now=NOW)

    assert "LIQUIDITY_IMPROVING" in {event.event_type for event in events}


def _snapshot(
    subject_id: str,
    state: CandidateLifecycleState,
    *,
    opportunity_score: float = 50,
    risk_score: float = 25,
    liquidity_score: float = 60,
    data_quality_score: float = 90,
    appearance_count: int = 1,
) -> CandidateSnapshot:
    return CandidateSnapshot(
        subject_id=subject_id,
        state=state,
        observed_at=NOW,
        opportunity_score=opportunity_score,
        risk_score=risk_score,
        liquidity_score=liquidity_score,
        data_quality_score=data_quality_score,
        appearance_count=appearance_count,
    )
