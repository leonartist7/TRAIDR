"""Models for local read-only intelligence reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class BriefingState(str, Enum):
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class DailyBriefing:
    state: BriefingState
    generated_at: datetime
    market_scan_summary: dict[str, Any]
    top_radar_candidates: tuple[dict[str, Any], ...]
    highest_risk_candidates: tuple[dict[str, Any], ...]
    new_alerts: tuple[dict[str, Any], ...]
    recent_simulation_results: tuple[dict[str, Any], ...]
    current_safety_status: dict[str, Any]
    missing_data_warnings: tuple[str, ...]
    suggested_watchlist: tuple[str, ...]
    next_commands: tuple[str, ...]
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "generated_at": self.generated_at.isoformat(),
            "market_scan_summary": self.market_scan_summary,
            "top_radar_candidates": [dict(row) for row in self.top_radar_candidates],
            "highest_risk_candidates": [dict(row) for row in self.highest_risk_candidates],
            "new_alerts": [dict(row) for row in self.new_alerts],
            "recent_simulation_results": [dict(row) for row in self.recent_simulation_results],
            "current_safety_status": dict(self.current_safety_status),
            "missing_data_warnings": list(self.missing_data_warnings),
            "suggested_watchlist": list(self.suggested_watchlist),
            "next_commands": list(self.next_commands),
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }
