"""Models for manual local portfolio analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ManualPortfolioEntry:
    entry_id: str
    symbol: str
    chain: str
    pair_ref: str
    entry_price: Decimal
    size_usd: Decimal
    thesis: str
    stop_zone: str
    take_profit_zone: str
    conviction: str
    risk_level: str
    notes: str
    created_at: datetime
    updated_at: datetime
    active: bool
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "symbol": self.symbol,
            "chain": self.chain,
            "pair_ref": self.pair_ref,
            "entry_price": str(self.entry_price),
            "size_usd": str(self.size_usd),
            "thesis": self.thesis,
            "stop_zone": self.stop_zone,
            "take_profit_zone": self.take_profit_zone,
            "conviction": self.conviction,
            "risk_level": self.risk_level,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "active": self.active,
            "can_execute_trades": self.can_execute_trades,
        }


@dataclass(frozen=True)
class PortfolioReport:
    total_exposure_usd: Decimal
    concentration_risk: str
    meme_exposure_usd: Decimal
    chain_exposure: dict[str, str]
    thesis_warnings: tuple[str, ...]
    stale_thesis_warnings: tuple[str, ...]
    entries: tuple[ManualPortfolioEntry, ...]
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_exposure_usd": str(self.total_exposure_usd),
            "concentration_risk": self.concentration_risk,
            "meme_exposure_usd": str(self.meme_exposure_usd),
            "chain_exposure": dict(self.chain_exposure),
            "thesis_warnings": list(self.thesis_warnings),
            "stale_thesis_warnings": list(self.stale_thesis_warnings),
            "entries": [entry.to_dict() for entry in self.entries],
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }
