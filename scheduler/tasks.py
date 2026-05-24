"""Research scheduler task definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class ScheduledTask:
    name: str
    interval: timedelta

    def is_due(self, *, now: datetime, last_run_at: datetime | None) -> bool:
        if last_run_at is None:
            return True
        return now - last_run_at >= self.interval


DEFAULT_TASKS: tuple[ScheduledTask, ...] = (
    ScheduledTask("watchlist_check", timedelta(minutes=1)),
    ScheduledTask("technical_update", timedelta(minutes=5)),
    ScheduledTask("radar_update", timedelta(minutes=15)),
    ScheduledTask("macro_news_update", timedelta(hours=1)),
    ScheduledTask("opportunity_report", timedelta(hours=4)),
    ScheduledTask("daily_report", timedelta(days=1)),
)

