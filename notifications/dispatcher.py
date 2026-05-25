"""Notification dispatcher that records local history and dedupes alerts."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from notifications.dedupe import AlertDeduper
from notifications.history import AlertHistory
from notifications.models import Alert, SendResult
from notifications.senders import LocalOnlySender


class Sender(Protocol):
    channel: str

    def send(self, alert: Alert) -> SendResult:
        ...


class NotificationDispatcher:
    def __init__(
        self,
        *,
        history: AlertHistory,
        senders: Iterable[Sender] = (),
        deduper: AlertDeduper | None = None,
    ) -> None:
        self.history = history
        self.senders = tuple(senders) or (LocalOnlySender(),)
        self.deduper = deduper or AlertDeduper()

    def dispatch(self, alert: Alert, *, now: datetime | None = None) -> tuple[SendResult, ...]:
        if not self.deduper.should_send(alert):
            result = SendResult("local", "DEDUPED", ("ALERT_DEDUPED",))
            self.history.record(alert, result, recorded_at=now)
            return (result,)
        results: list[SendResult] = []
        for sender in self.senders:
            result = sender.send(alert)
            self.history.record(alert, result, recorded_at=now)
            results.append(result)
        return tuple(results)

    def dispatch_many(self, alerts: Iterable[Alert], *, now: datetime | None = None) -> tuple[SendResult, ...]:
        results: list[SendResult] = []
        for alert in alerts:
            results.extend(self.dispatch(alert, now=now))
        return tuple(results)
