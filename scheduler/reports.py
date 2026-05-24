"""Research report generation for local intelligence runs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def build_research_report(
    *,
    report_type: str,
    radar_states: Iterable[Mapping[str, Any]],
    macro_news: Mapping[str, Any] | None = None,
    alerts: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    states = tuple(radar_states)
    high_risk_count = sum(1 for state in states if state.get("state") == "AVOID")
    candidate_count = sum(1 for state in states if state.get("state") == "BUY_CANDIDATE")
    return {
        "report_type": report_type,
        "status": "OK" if states else "INSUFFICIENT_DATA",
        "candidate_count": candidate_count,
        "high_risk_count": high_risk_count,
        "radar_states": [dict(state) for state in states],
        "macro_news": dict(macro_news or {}),
        "alerts": [dict(alert) for alert in alerts],
        "can_execute_trades": False,
    }

