"""Deterministic lifecycle transition detection."""

from __future__ import annotations

from datetime import datetime, timezone

from lifecycle.models import CandidateLifecycleState, CandidateSnapshot, LifecycleEvent


def detect_lifecycle_events(
    *,
    previous: CandidateSnapshot | None,
    current: CandidateSnapshot | None,
    now: datetime | None = None,
) -> tuple[LifecycleEvent, ...]:
    observed_at = _aware(now or (current.observed_at if current else previous.observed_at if previous else datetime.now(timezone.utc)))
    if previous is None and current is None:
        return ()
    if current is None:
        assert previous is not None
        return (
            _event(
                previous.subject_id,
                "CANDIDATE_DISAPPEARED",
                previous.state,
                CandidateLifecycleState.STALE,
                observed_at,
                ("CANDIDATE_DISAPPEARED",),
                {"previous": previous.to_dict()},
            ),
        )
    if previous is None:
        return (
            _event(
                current.subject_id,
                "CANDIDATE_DISCOVERED",
                None,
                current.state if current.state != CandidateLifecycleState.STALE else CandidateLifecycleState.STALE,
                observed_at,
                ("CANDIDATE_DISCOVERED",),
                {"current": current.to_dict()},
            ),
        )

    events: list[LifecycleEvent] = []
    if current.state != previous.state:
        events.append(
            _event(
                current.subject_id,
                "STATE_CHANGED",
                previous.state,
                current.state,
                observed_at,
                (f"STATE_{previous.state.value}_TO_{current.state.value}",),
                {"previous": previous.to_dict(), "current": current.to_dict()},
            )
        )
    if current.opportunity_score - previous.opportunity_score >= 10:
        events.append(_metric_event(previous, current, observed_at, "OPPORTUNITY_IMPROVING", "OPPORTUNITY_IMPROVED"))
    if current.risk_score - previous.risk_score >= 10:
        target = CandidateLifecycleState.EXIT_RISK if current.risk_score >= 75 else current.state
        events.append(_metric_event(previous, current, observed_at, "RISK_INCREASING", "RISK_INCREASED", target))
    if current.liquidity_score >= previous.liquidity_score * 1.2 and current.liquidity_score - previous.liquidity_score >= 5:
        events.append(_metric_event(previous, current, observed_at, "LIQUIDITY_IMPROVING", "LIQUIDITY_IMPROVED"))
    if current.liquidity_score <= previous.liquidity_score * 0.8 and previous.liquidity_score - current.liquidity_score >= 5:
        events.append(_metric_event(previous, current, observed_at, "LIQUIDITY_DRAINING", "LIQUIDITY_DRAINED", CandidateLifecycleState.REVIEW))
    if current.data_quality_score < 40 or current.state is CandidateLifecycleState.STALE:
        events.append(_metric_event(previous, current, observed_at, "STALE_DATA", "STALE_DATA_DETECTED", CandidateLifecycleState.STALE))
    if current.appearance_count > previous.appearance_count:
        events.append(_metric_event(previous, current, observed_at, "REPEATED_APPEARANCE", "REPEATED_CANDIDATE_APPEARANCE"))
    return tuple(events)


def _metric_event(
    previous: CandidateSnapshot,
    current: CandidateSnapshot,
    observed_at: datetime,
    event_type: str,
    reason: str,
    to_state: CandidateLifecycleState | None = None,
) -> LifecycleEvent:
    return _event(
        current.subject_id,
        event_type,
        previous.state,
        to_state or current.state,
        observed_at,
        (reason,),
        {"previous": previous.to_dict(), "current": current.to_dict()},
    )


def _event(
    subject_id: str,
    event_type: str,
    from_state: CandidateLifecycleState | None,
    to_state: CandidateLifecycleState,
    observed_at: datetime,
    reason_codes: tuple[str, ...],
    payload: dict,
) -> LifecycleEvent:
    return LifecycleEvent(
        subject_id=subject_id,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        observed_at=observed_at,
        reason_codes=reason_codes,
        payload={**payload, "can_execute_trades": False},
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
