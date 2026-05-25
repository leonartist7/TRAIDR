"""Templates for research-only alert messages."""

from __future__ import annotations

from notifications.models import Alert, AlertSeverity

from alerts.rules import AlertRuleMatch


def alert_from_match(match: AlertRuleMatch) -> Alert:
    return Alert(
        subject_id=match.subject_id,
        state=match.current.state,
        severity=AlertSeverity(match.severity),
        reason_codes=match.reason_codes,
        message=_message(match),
    )


def _message(match: AlertRuleMatch) -> str:
    previous = match.previous
    current = match.current
    if previous is None:
        return f"{current.subject_id}: {match.rule_id.value} detected in local research data."
    return (
        f"{current.subject_id}: {match.rule_id.value}. "
        f"State {previous.state} -> {current.state}; "
        f"opportunity {previous.opportunity_score:.1f} -> {current.opportunity_score:.1f}; "
        f"risk {previous.risk_score:.1f} -> {current.risk_score:.1f}. "
        "Research-only alert; no execution action."
    )
