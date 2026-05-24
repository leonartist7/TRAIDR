"""Read-only token discovery result models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class DiscoveryCandidate:
    pair_id: str
    chain: str
    base_symbol: str
    quote_symbol: str
    price_usd: Decimal | None
    liquidity_usd: Decimal | None
    volume_24h_usd: Decimal | None
    source: str
    observed_at: datetime
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "chain": self.chain,
            "base_symbol": self.base_symbol,
            "quote_symbol": self.quote_symbol,
            "price_usd": str(self.price_usd) if self.price_usd is not None else None,
            "liquidity_usd": str(self.liquidity_usd) if self.liquidity_usd is not None else None,
            "volume_24h_usd": str(self.volume_24h_usd) if self.volume_24h_usd is not None else None,
            "source": self.source,
            "observed_at": self.observed_at.isoformat(),
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }

    @property
    def missing_metric_count(self) -> int:
        return sum(
            value is None
            for value in (self.price_usd, self.liquidity_usd, self.volume_24h_usd)
        )


@dataclass(frozen=True)
class TokenDiscoveryResult:
    status: str
    candidates: tuple[DiscoveryCandidate, ...]
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }

