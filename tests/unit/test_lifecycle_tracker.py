from datetime import datetime, timezone

from lifecycle.models import CandidateLifecycleState, CandidateSnapshot
from lifecycle.tracker import LifecycleTracker
from storage.duckdb_store import DuckDBStore
from storage.schema import initialize_schema, list_tables


NOW = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)


def test_lifecycle_tracker_returns_events_without_database() -> None:
    tracker = LifecycleTracker()

    events = tracker.track(previous=None, current=_snapshot("token-a"))

    assert len(events) == 1
    assert events[0].event_type == "CANDIDATE_DISCOVERED"


def test_lifecycle_tracker_persists_events_to_duckdb() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        assert "lifecycle_events" in list_tables(store.connection)
        tracker = LifecycleTracker(store.connection)
        previous = _snapshot("token-a", risk_score=20)
        current = _snapshot("token-a", risk_score=85, state=CandidateLifecycleState.REVIEW)

        events = tracker.track(previous=previous, current=current, now=NOW)
        rows = store.connection.execute(
            """
            SELECT subject_id, event_type, to_state, payload_json
            FROM lifecycle_events
            ORDER BY recorded_at
            """
        ).fetchall()

    assert len(events) >= 2
    assert any(row[1] == "RISK_INCREASING" for row in rows)
    assert any(row[2] == "EXIT_RISK" for row in rows)
    assert "can_execute_trades" in rows[0][3]


def _snapshot(
    subject_id: str,
    *,
    state: CandidateLifecycleState = CandidateLifecycleState.WATCH,
    risk_score: float = 25,
) -> CandidateSnapshot:
    return CandidateSnapshot(
        subject_id=subject_id,
        state=state,
        observed_at=NOW,
        opportunity_score=50,
        risk_score=risk_score,
        liquidity_score=60,
        data_quality_score=90,
    )
