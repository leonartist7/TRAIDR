"""Rule engine for local research alerts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from alerts.alert_templates import alert_from_match
from alerts.rules import AlertRuleMatch, ResearchAlertSnapshot, evaluate_alert_rules
from notifications.dispatcher import NotificationDispatcher
from notifications.models import SendResult


@dataclass(frozen=True)
class AlertRuleEngineResult:
    matches: tuple[AlertRuleMatch, ...]
    send_results: tuple[SendResult, ...]
    can_execute_trades: bool = False

    @property
    def alerts_created(self) -> int:
        return sum(1 for result in self.send_results if result.status != "DEDUPED")


class ResearchAlertRuleEngine:
    def __init__(self, dispatcher: NotificationDispatcher) -> None:
        self.dispatcher = dispatcher

    def evaluate_and_dispatch(
        self,
        *,
        previous: ResearchAlertSnapshot | None,
        current: ResearchAlertSnapshot,
        now: datetime | None = None,
    ) -> AlertRuleEngineResult:
        matches = evaluate_alert_rules(previous, current)
        results: list[SendResult] = []
        for match in matches:
            results.extend(self.dispatcher.dispatch(alert_from_match(match), now=now))
        return AlertRuleEngineResult(matches=matches, send_results=tuple(results))
