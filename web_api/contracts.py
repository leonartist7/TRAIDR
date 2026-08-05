"""Pydantic contracts for the read-only TRAIDR web API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

ApiStatus = Literal["OK", "DEGRADED", "NO_TRADE", "INSUFFICIENT_DATA", "ERROR"]
FreshnessState = Literal["FRESH", "STALE", "UNKNOWN"]


class ReadModel(BaseModel):
    """Base model that rejects undeclared response fields."""

    model_config = ConfigDict(extra="forbid")


class FreshnessInfo(ReadModel):
    state: FreshnessState
    observed_at: datetime | None = None
    age_seconds: float | None = Field(default=None, ge=0)
    maximum_age_seconds: float | None = Field(default=None, gt=0)


ModelT = TypeVar("ModelT")


class ApiEnvelope(ReadModel, Generic[ModelT]):
    status: ApiStatus
    as_of: datetime
    data: ModelT
    freshness: dict[str, FreshnessInfo] = Field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
    can_execute_trades: Literal[False] = False
    request_id: str = Field(min_length=1, max_length=128)


class StatusData(ReadModel):
    database_exists: bool
    table_count: int = Field(ge=0)
    service_state: str
    latest_heartbeat: datetime | None = None
    provider_health: list[dict[str, Any]] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)


class ShadowEvidenceData(ReadModel):
    provider: str
    observed_at: datetime | None = None
    freshness: FreshnessState = "UNKNOWN"
    setup_class: str = "INSUFFICIENT_DATA"
    market_regime: str = "INSUFFICIENT_DATA"
    crowding_score: float | None = None
    squeeze_risk: float | None = None
    catalyst_risk: float | None = None
    data_quality_score: float = 0.0
    probability_state: str = "UNCALIBRATED"
    scoring_weight: float = Field(default=0.0, ge=0.0, le=0.0)
    fields: dict[str, float] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    can_execute_trades: Literal[False] = False


class ScannerFactorData(ReadModel):
    factor: str
    weight: float
    raw_value: float | None = None
    normalized_value: float | None = None
    long_contribution: float = 0.0
    short_contribution: float = 0.0
    explanation: str
    source: str | None = None
    reason_codes: list[str] = Field(default_factory=list)


class ScannerRow(ReadModel):
    score_id: str
    instrument_id: str
    observed_at: datetime | None = None
    recorded_at: datetime | None = None
    status: str
    direction: str
    score: float | None = None
    long_score: float | None = None
    short_score: float | None = None
    risk_score: float | None = None
    conflicts: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    factors: list[ScannerFactorData] = Field(default_factory=list)
    shadow: ShadowEvidenceData | None = None
    can_execute_trades: Literal[False] = False


class ScannerData(ReadModel):
    rows: list[ScannerRow] = Field(default_factory=list)
    limit: int = Field(ge=1, le=2_000)
    total: int = Field(ge=0)


class OverviewData(ReadModel):
    scanner: list[ScannerRow] = Field(default_factory=list)
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    paper_positions: list[dict[str, Any]] = Field(default_factory=list)
    service_heartbeats: list[dict[str, Any]] = Field(default_factory=list)
    shadow_evidence: list[ShadowEvidenceData] = Field(default_factory=list)
    news: list[dict[str, Any]] = Field(default_factory=list)


class CandleData(ReadModel):
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    base_volume: float
    quote_volume: float
    source: str
    received_at: datetime
    quality: str
    can_execute_trades: Literal[False] = False


class MarketData(ReadModel):
    instrument_id: str
    interval: str
    candles: list[CandleData] = Field(default_factory=list)
    scanner: ScannerRow | None = None
    microstructure: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class MarketInstrumentData(ReadModel):
    instrument_id: str
    source: str
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    discovered_at: datetime
    refreshed_at: datetime
    can_execute_trades: Literal[False] = False


class MarketsData(ReadModel):
    instruments: list[MarketInstrumentData] = Field(default_factory=list)
    limit: int = Field(ge=1, le=2_000)
    total: int = Field(ge=0)


class ErrorData(ReadModel):
    code: str
    message: str
