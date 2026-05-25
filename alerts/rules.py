"""Research alert rules for radar, watchlist, and scan changes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any


class AlertRuleId(str, Enum):
    OPPORTUNITY_INCREASED = "OPPORTUNITY_INCREASED"
    RISK_INCREASED = "RISK_INCREASED"
    LIQUIDITY_DROPPED = "LIQUIDITY_DROPPED"
    LIQUIDITY_INCREASED = "LIQUIDITY_INCREASED"
    WATCH_TO_ALERT = "WATCH_TO_ALERT"
    ALERT_TO_BUY_CANDIDATE = "ALERT_TO_BUY_CANDIDATE"
    MOVED_TO_AVOID = "MOVED_TO_AVOID"
    SCAN_DATA_STALE = "SCAN_DATA_STALE"
    SAFETY_DATA_INCOMPLETE = "SAFETY_DATA_INCOMPLETE"


@dataclass(frozen=True)
class ResearchAlertSnapshot:
    subject_id: str
    state: str
    opportunity_score: float
    risk_score: float
    liquidity_usd: Decimal | None = None
    data_quality: str = "sufficient"
    safety_complete: bool | None = True
    reason_codes: tuple[str, ...] = ()
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "state": self.state,
            "opportunity_score": self.opportunity_score,
            "risk_score": self.risk_score,
            "liquidity_usd": str(self.liquidity_usd) if self.liquidity_usd is not None else None,
            "data_quality": self.data_quality,
            "safety_complete": self.safety_complete,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }


@dataclass(frozen=True)
class AlertRuleMatch:
    rule_id: AlertRuleId
    subject_id: str
    severity: str
    reason_codes: tuple[str, ...]
    previous: ResearchAlertSnapshot | None
    current: ResearchAlertSnapshot
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id.value,
            "subject_id": self.subject_id,
            "severity": self.severity,
            "reason_codes": list(self.reason_codes),
            "previous": self.previous.to_dict() if self.previous else None,
            "current": self.current.to_dict(),
            "can_execute_trades": self.can_execute_trades,
        }


OPPORTUNITY_SCORE_DELTA = 15.0
RISK_SCORE_DELTA = 15.0
LIQUIDITY_DELTA_RATIO = Decimal("0.25")


def evaluate_alert_rules(
    previous: ResearchAlertSnapshot | None,
    current: ResearchAlertSnapshot,
) -> tuple[AlertRuleMatch, ...]:
    matches: list[AlertRuleMatch] = []
    if previous is not None:
        if current.opportunity_score - previous.opportunity_score >= OPPORTUNITY_SCORE_DELTA:
            matches.append(_match(AlertRuleId.OPPORTUNITY_INCREASED, "INFO", previous, current))
        if current.risk_score - previous.risk_score >= RISK_SCORE_DELTA:
            matches.append(_match(AlertRuleId.RISK_INCREASED, "WARNING", previous, current))
        if _liquidity_dropped(previous, current):
            matches.append(_match(AlertRuleId.LIQUIDITY_DROPPED, "WARNING", previous, current))
        if _liquidity_increased(previous, current):
            matches.append(_match(AlertRuleId.LIQUIDITY_INCREASED, "INFO", previous, current))
        if previous.state == "WATCH" and current.state == "ALERT":
            matches.append(_match(AlertRuleId.WATCH_TO_ALERT, "INFO", previous, current))
        if previous.state == "ALERT" and current.state == "BUY_CANDIDATE":
            matches.append(_match(AlertRuleId.ALERT_TO_BUY_CANDIDATE, "INFO", previous, current))
        if previous.state != "AVOID" and current.state == "AVOID":
            matches.append(_match(AlertRuleId.MOVED_TO_AVOID, "CRITICAL", previous, current))
    if current.data_quality == "stale":
        matches.append(_match(AlertRuleId.SCAN_DATA_STALE, "WARNING", previous, current))
    if current.safety_complete is not True:
        matches.append(_match(AlertRuleId.SAFETY_DATA_INCOMPLETE, "WARNING", previous, current))
    return tuple(matches)


def all_rule_descriptions() -> tuple[dict[str, str], ...]:
    return (
        {"rule_id": AlertRuleId.OPPORTUNITY_INCREASED.value, "description": "Opportunity score increased meaningfully."},
        {"rule_id": AlertRuleId.RISK_INCREASED.value, "description": "Risk score increased meaningfully."},
        {"rule_id": AlertRuleId.LIQUIDITY_DROPPED.value, "description": "Liquidity dropped by at least 25 percent."},
        {"rule_id": AlertRuleId.LIQUIDITY_INCREASED.value, "description": "Liquidity increased by at least 25 percent."},
        {"rule_id": AlertRuleId.WATCH_TO_ALERT.value, "description": "Token moved from WATCH to ALERT."},
        {"rule_id": AlertRuleId.ALERT_TO_BUY_CANDIDATE.value, "description": "Token moved from ALERT to BUY_CANDIDATE."},
        {"rule_id": AlertRuleId.MOVED_TO_AVOID.value, "description": "Token moved from any non-AVOID state to AVOID."},
        {"rule_id": AlertRuleId.SCAN_DATA_STALE.value, "description": "Scan data became stale."},
        {"rule_id": AlertRuleId.SAFETY_DATA_INCOMPLETE.value, "description": "Safety data is incomplete or unknown."},
    )


def _match(
    rule_id: AlertRuleId,
    severity: str,
    previous: ResearchAlertSnapshot | None,
    current: ResearchAlertSnapshot,
) -> AlertRuleMatch:
    return AlertRuleMatch(
        rule_id=rule_id,
        subject_id=current.subject_id,
        severity=severity,
        reason_codes=(rule_id.value, "RESEARCH_ALERT_ONLY", "NO_EXECUTION_ACTION"),
        previous=previous,
        current=current,
    )


def _liquidity_dropped(previous: ResearchAlertSnapshot, current: ResearchAlertSnapshot) -> bool:
    if previous.liquidity_usd is None or current.liquidity_usd is None:
        return False
    if previous.liquidity_usd <= 0:
        return False
    return (previous.liquidity_usd - current.liquidity_usd) / previous.liquidity_usd >= LIQUIDITY_DELTA_RATIO


def _liquidity_increased(previous: ResearchAlertSnapshot, current: ResearchAlertSnapshot) -> bool:
    if previous.liquidity_usd is None or current.liquidity_usd is None:
        return False
    if previous.liquidity_usd <= 0:
        return False
    return (current.liquidity_usd - previous.liquidity_usd) / previous.liquidity_usd >= LIQUIDITY_DELTA_RATIO
