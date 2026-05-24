"""Read-only market scan result models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from data_pipeline.contracts import DataQuality, NormalizedMarketSnapshot


@dataclass(frozen=True)
class MarketScanCandidate:
    token_pair_id: str
    source: str
    observed_at: datetime
    price_usd: Decimal | None
    liquidity_usd: Decimal | None
    volume_24h_usd: Decimal | None
    data_quality: str
    reason_codes: tuple[str, ...]
    snapshot: NormalizedMarketSnapshot | None = None
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_pair_id": self.token_pair_id,
            "source": self.source,
            "observed_at": self.observed_at.isoformat(),
            "price_usd": str(self.price_usd) if self.price_usd is not None else None,
            "liquidity_usd": str(self.liquidity_usd) if self.liquidity_usd is not None else None,
            "volume_24h_usd": str(self.volume_24h_usd) if self.volume_24h_usd is not None else None,
            "data_quality": self.data_quality,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }

    @classmethod
    def from_snapshot(cls, snapshot: NormalizedMarketSnapshot) -> "MarketScanCandidate":
        quality = snapshot.freshness.quality.value
        reasons = (
            "SCAN_CANDIDATE_NORMALIZED",
            "READ_ONLY_MARKET_DATA",
        )
        if snapshot.freshness.quality is not DataQuality.SUFFICIENT:
            reasons = ("SCAN_CANDIDATE_INSUFFICIENT_DATA",)
        return cls(
            token_pair_id=snapshot.identity.pair_id,
            source=snapshot.provenance.source_name,
            observed_at=snapshot.freshness.observed_at,
            price_usd=snapshot.metrics.price_usd,
            liquidity_usd=snapshot.metrics.liquidity_usd,
            volume_24h_usd=snapshot.metrics.volume_24h_usd,
            data_quality=quality,
            reason_codes=reasons,
            snapshot=snapshot,
        )


@dataclass(frozen=True)
class MarketScanResult:
    status: str
    candidates: tuple[MarketScanCandidate, ...]
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }

