"""Models for read-only token detail intelligence cards."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class TokenIdentity:
    pair_id: str
    chain: str
    base_symbol: str
    quote_symbol: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {
            "pair_id": self.pair_id,
            "chain": self.chain,
            "base_symbol": self.base_symbol,
            "quote_symbol": self.quote_symbol,
            "source": self.source,
        }


@dataclass(frozen=True)
class AntiRugDetailStatus:
    status: str
    unknown_fields: tuple[str, ...]
    hard_fail_reasons: tuple[str, ...]
    insufficient_data_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "unknown_fields": list(self.unknown_fields),
            "hard_fail_reasons": list(self.hard_fail_reasons),
            "insufficient_data_reasons": list(self.insufficient_data_reasons),
        }


@dataclass(frozen=True)
class TokenDetailReport:
    status: str
    identity: TokenIdentity | None
    price_usd: Decimal | None
    liquidity_usd: Decimal | None
    volume_24h_usd: Decimal | None
    technical_vector: dict[str, Any] | None
    technical_vector_status: str
    liquidity_score: float
    opportunity_score: float
    risk_score: float
    anti_rug: AntiRugDetailStatus
    radar_state: str
    reason_codes: tuple[str, ...]
    why_interesting: str
    why_risky: str
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "identity": self.identity.to_dict() if self.identity else None,
            "price_usd": str(self.price_usd) if self.price_usd is not None else None,
            "liquidity_usd": str(self.liquidity_usd) if self.liquidity_usd is not None else None,
            "volume_24h_usd": str(self.volume_24h_usd) if self.volume_24h_usd is not None else None,
            "technical_vector": self.technical_vector,
            "technical_vector_status": self.technical_vector_status,
            "liquidity_score": self.liquidity_score,
            "opportunity_score": self.opportunity_score,
            "risk_score": self.risk_score,
            "anti_rug": self.anti_rug.to_dict(),
            "radar_state": self.radar_state,
            "reason_codes": list(self.reason_codes),
            "why_interesting": self.why_interesting,
            "why_risky": self.why_risky,
            "can_execute_trades": self.can_execute_trades,
        }
