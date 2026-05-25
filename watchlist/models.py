"""Models for local read-only watchlists."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class WatchEntry:
    pair_ref: str
    note: str
    tags: tuple[str, ...]
    created_at: datetime
    active: bool
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_ref": self.pair_ref,
            "note": self.note,
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat(),
            "active": self.active,
            "can_execute_trades": self.can_execute_trades,
        }


@dataclass(frozen=True)
class WatchScanRecord:
    pair_ref: str
    scanned_at: datetime
    status: str
    radar_state: str
    opportunity_score: float
    risk_score: float
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_ref": self.pair_ref,
            "scanned_at": self.scanned_at.isoformat(),
            "status": self.status,
            "radar_state": self.radar_state,
            "opportunity_score": self.opportunity_score,
            "risk_score": self.risk_score,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }


@dataclass(frozen=True)
class WatchScanResult:
    status: str
    scanned: tuple[WatchScanRecord, ...]
    alerts_created: tuple[str, ...]
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "scanned": [record.to_dict() for record in self.scanned],
            "alerts_created": list(self.alerts_created),
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }
