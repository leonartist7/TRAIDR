"""Local event calendar abstraction with freshness-aware outputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    subject_id: str
    event_type: str
    scheduled_at: datetime
    impact: str
    summary: str

    def to_dict(self) -> dict[str, str]:
        return {
            "event_id": self.event_id,
            "subject_id": self.subject_id,
            "event_type": self.event_type,
            "scheduled_at": self.scheduled_at.isoformat(),
            "impact": self.impact,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class CalendarResult:
    status: str
    events: tuple[CalendarEvent, ...]
    confidence: float
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "events": [event.to_dict() for event in self.events],
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": False,
        }


def build_event_calendar(
    records: Iterable[Mapping[str, Any]],
    *,
    now: datetime,
    freshness_window: timedelta = timedelta(days=7),
) -> CalendarResult:
    if now.tzinfo is None or now.utcoffset() is None:
        return CalendarResult("INSUFFICIENT_DATA", (), 0.0, ("CALENDAR_NOW_NAIVE",))
    events: list[CalendarEvent] = []
    stale = 0
    malformed = 0
    for record in records:
        event = _parse_event(record)
        if event is None:
            malformed += 1
            continue
        if event.scheduled_at < now - freshness_window:
            stale += 1
            continue
        events.append(event)
    if not events:
        reasons = ["CALENDAR_EVENTS_MISSING"]
        if stale:
            reasons.append("CALENDAR_EVENTS_STALE")
        if malformed:
            reasons.append("CALENDAR_EVENTS_MALFORMED")
        return CalendarResult("INSUFFICIENT_DATA", (), 0.0, tuple(reasons))
    reasons = ["CALENDAR_EVENTS_AVAILABLE"]
    confidence = 1.0
    if stale or malformed:
        reasons.append("CALENDAR_EVENTS_PARTIAL")
        confidence = 0.7
    return CalendarResult("OK", tuple(events), confidence, tuple(reasons))


def _parse_event(record: Mapping[str, Any]) -> CalendarEvent | None:
    try:
        event_id = str(record["event_id"])
        subject_id = str(record.get("subject_id", "market"))
        event_type = str(record["event_type"])
        impact = str(record.get("impact", "unknown"))
        summary = str(record.get("summary", ""))
        scheduled_raw = record["scheduled_at"]
        scheduled_at = (
            scheduled_raw
            if isinstance(scheduled_raw, datetime)
            else datetime.fromisoformat(str(scheduled_raw))
        )
        if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        return None
    return CalendarEvent(event_id, subject_id, event_type, scheduled_at.astimezone(timezone.utc), impact, summary)

