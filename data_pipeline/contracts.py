"""Normalized market data contracts and safe adapter results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Generic, TypeVar

from risk.models import MarketDataState

T = TypeVar("T")


class DataQuality(str, Enum):
    SUFFICIENT = "sufficient"
    MISSING = "missing"
    STALE = "stale"
    MALFORMED = "malformed"
    CONTRADICTORY = "contradictory"
    UNCERTAIN = "uncertain"


class AdapterStatus(str, Enum):
    OK = "OK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class MarketIdentity:
    pair_id: str
    chain_id: str
    base_symbol: str
    quote_symbol: str


@dataclass(frozen=True)
class MarketMetrics:
    price_usd: Decimal
    liquidity_usd: Decimal
    volume_24h_usd: Decimal


@dataclass(frozen=True)
class DataProvenance:
    source_name: str
    source_record_id: str
    retrieved_at: datetime
    raw_status: str


@dataclass(frozen=True)
class FreshnessFields:
    observed_at: datetime
    normalized_at: datetime
    quality: DataQuality


@dataclass(frozen=True)
class NormalizedMarketSnapshot:
    identity: MarketIdentity
    metrics: MarketMetrics
    provenance: DataProvenance
    freshness: FreshnessFields

    def market_data_state(self) -> MarketDataState:
        return MarketDataState(
            observed_at=self.freshness.observed_at,
            provenance_known=True,
            malformed=self.freshness.quality is DataQuality.MALFORMED,
            contradictory=self.freshness.quality is DataQuality.CONTRADICTORY,
            uncertain=self.freshness.quality is DataQuality.UNCERTAIN,
        )

    def toon_summary(self) -> dict[str, str | float]:
        return {
            "pair": self.identity.pair_id,
            "chain": self.identity.chain_id,
            "base": self.identity.base_symbol,
            "quote": self.identity.quote_symbol,
            "px": float(self.metrics.price_usd),
            "liq": float(self.metrics.liquidity_usd),
            "vol24": float(self.metrics.volume_24h_usd),
            "src": self.provenance.source_name,
            "obs": self.freshness.observed_at.isoformat(),
        }


@dataclass(frozen=True)
class AdapterResult(Generic[T]):
    status: AdapterStatus
    reason_codes: tuple[str, ...]
    value: T | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        if not self.reason_codes:
            raise ValueError("adapter results require reason codes")
        if self.status is AdapterStatus.OK and self.value is None:
            raise ValueError("successful adapter results require a value")
        if self.status is not AdapterStatus.OK and self.value is not None:
            raise ValueError("insufficient adapter results cannot carry values")

    @property
    def ok(self) -> bool:
        return self.status is AdapterStatus.OK

    @classmethod
    def success(cls, value: T) -> "AdapterResult[T]":
        return cls(AdapterStatus.OK, ("ADAPTER_OK",), value)

    @classmethod
    def insufficient(cls, *reason_codes: str) -> "AdapterResult[T]":
        return cls(AdapterStatus.INSUFFICIENT_DATA, tuple(reason_codes))

