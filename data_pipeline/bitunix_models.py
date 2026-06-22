"""Strict read-only Bitunix futures market models."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, TypeAlias

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

BITUNIX_ALLOWED_SYMBOLS = ("HYPEUSDT", "BTCUSDT")
BITUNIX_ALLOWED_INTERVALS = ("1m", "5m", "15m", "1h")
BITUNIX_ALLOWED_DEPTH_LIMITS = ("1", "5", "15", "50", "max")
BITUNIX_INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}


class BitunixBaseModel(BaseModel):
    """Base model that hardcodes non-execution for every Bitunix payload."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    can_execute_trades: Literal[False] = False

    def safe_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict with non-execution explicitly preserved."""

        return _json_safe(self.model_dump(mode="python"))


class BitunixTicker(BitunixBaseModel):
    symbol: str
    mark_price: Decimal = Field(validation_alias=AliasChoices("markPrice", "mark_price"))
    last_price: Decimal = Field(validation_alias=AliasChoices("lastPrice", "last_price"))
    open_price: Decimal = Field(validation_alias=AliasChoices("open", "openPrice", "open_price"))
    last: Decimal
    quote_volume: Decimal = Field(validation_alias=AliasChoices("quoteVol", "quote_volume"))
    base_volume: Decimal = Field(validation_alias=AliasChoices("baseVol", "base_volume"))
    high: Decimal
    low: Decimal
    observed_at: datetime

    @field_validator("symbol")
    @classmethod
    def _valid_symbol(cls, value: str) -> str:
        return _validate_symbol(value)

    @model_validator(mode="after")
    def _valid_range(self) -> "BitunixTicker":
        if self.high < self.low:
            raise ValueError("ticker high cannot be below low")
        if self.last_price <= 0 or self.mark_price <= 0:
            raise ValueError("ticker prices must be positive")
        return self


class BitunixCandle(BitunixBaseModel):
    symbol: str
    interval: str
    time_ms: int = Field(validation_alias=AliasChoices("time", "time_ms"))
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    quote_volume: Decimal = Field(validation_alias=AliasChoices("quoteVol", "quote_volume", "q"))
    base_volume: Decimal = Field(validation_alias=AliasChoices("baseVol", "base_volume", "b"))
    price_type: str = Field(default="LAST_PRICE", validation_alias=AliasChoices("type", "price_type"))

    @field_validator("symbol")
    @classmethod
    def _valid_symbol(cls, value: str) -> str:
        return _validate_symbol(value)

    @field_validator("interval")
    @classmethod
    def _valid_interval(cls, value: str) -> str:
        return _validate_interval(value)

    @model_validator(mode="after")
    def _valid_ohlc(self) -> "BitunixCandle":
        if self.time_ms <= 0:
            raise ValueError("candle time must be positive")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("candle prices must be positive")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("candle high is contradictory")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("candle low is contradictory")
        if self.quote_volume < 0 or self.base_volume < 0:
            raise ValueError("candle volumes cannot be negative")
        return self

    @property
    def observed_at(self) -> datetime:
        return datetime.fromtimestamp(self.time_ms / 1000, tz=UTC)

    def chart_dict(self) -> dict[str, float | int]:
        return {
            "time": int(self.time_ms / 1000),
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.base_volume),
        }


class BitunixFundingRate(BitunixBaseModel):
    symbol: str
    mark_price: Decimal = Field(validation_alias=AliasChoices("markPrice", "mark_price"))
    last_price: Decimal = Field(validation_alias=AliasChoices("lastPrice", "last_price"))
    funding_rate: Decimal = Field(validation_alias=AliasChoices("fundingRate", "funding_rate"))
    funding_interval_hours: int = Field(validation_alias=AliasChoices("fundingInterval", "funding_interval_hours"))
    next_funding_time_ms: int = Field(validation_alias=AliasChoices("nextFundingTime", "next_funding_time_ms"))
    max_funding_rate: Decimal = Field(validation_alias=AliasChoices("maxFundingRate", "max_funding_rate"))
    min_funding_rate: Decimal = Field(validation_alias=AliasChoices("minFundingRate", "min_funding_rate"))
    observed_at: datetime

    @field_validator("symbol")
    @classmethod
    def _valid_symbol(cls, value: str) -> str:
        return _validate_symbol(value)

    @model_validator(mode="after")
    def _valid_funding(self) -> "BitunixFundingRate":
        if self.mark_price <= 0 or self.last_price <= 0:
            raise ValueError("funding prices must be positive")
        if self.funding_interval_hours <= 0:
            raise ValueError("funding interval must be positive")
        if self.next_funding_time_ms <= 0:
            raise ValueError("next funding time must be positive")
        return self

    @property
    def next_funding_at(self) -> datetime:
        return datetime.fromtimestamp(self.next_funding_time_ms / 1000, tz=UTC)


class BitunixOrderBookLevel(BitunixBaseModel):
    price: Decimal
    amount: Decimal

    @model_validator(mode="after")
    def _valid_level(self) -> "BitunixOrderBookLevel":
        if self.price <= 0:
            raise ValueError("order book price must be positive")
        if self.amount < 0:
            raise ValueError("order book amount cannot be negative")
        return self

    @classmethod
    def from_raw(cls, value: Any) -> "BitunixOrderBookLevel":
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError("order book level must be a two-item array")
        return cls(price=value[0], amount=value[1])


class BitunixDepthDelta(BitunixBaseModel):
    symbol: str
    bid_sum: Decimal
    ask_sum: Decimal
    depth_delta_percent: Decimal
    observed_at: datetime

    @field_validator("symbol")
    @classmethod
    def _valid_symbol(cls, value: str) -> str:
        return _validate_symbol(value)


class BitunixDepthSnapshot(BitunixBaseModel):
    symbol: str
    bids: tuple[BitunixOrderBookLevel, ...]
    asks: tuple[BitunixOrderBookLevel, ...]
    observed_at: datetime

    @field_validator("symbol")
    @classmethod
    def _valid_symbol(cls, value: str) -> str:
        return _validate_symbol(value)

    @model_validator(mode="after")
    def _valid_depth(self) -> "BitunixDepthSnapshot":
        if not self.bids or not self.asks:
            raise ValueError("depth requires bids and asks")
        return self

    def depth_delta(self) -> BitunixDepthDelta:
        bid_sum = sum((level.amount for level in self.bids), Decimal("0"))
        ask_sum = sum((level.amount for level in self.asks), Decimal("0"))
        denominator = bid_sum + ask_sum
        if denominator <= 0:
            raise ValueError("depth denominator must be positive")
        return BitunixDepthDelta(
            symbol=self.symbol,
            bid_sum=bid_sum,
            ask_sum=ask_sum,
            depth_delta_percent=(bid_sum / denominator) * Decimal("100"),
            observed_at=self.observed_at,
        )


class BitunixCockpitSnapshot(BitunixBaseModel):
    symbol: str
    interval: str
    ticker: BitunixTicker
    candles: tuple[BitunixCandle, ...]
    funding_rate: BitunixFundingRate
    depth: BitunixDepthSnapshot
    depth_delta: BitunixDepthDelta
    opportunity_rating: int
    risk_rating: int
    reason_codes: tuple[str, ...]
    observed_at: datetime

    @field_validator("symbol")
    @classmethod
    def _valid_symbol(cls, value: str) -> str:
        return _validate_symbol(value)

    @field_validator("interval")
    @classmethod
    def _valid_interval(cls, value: str) -> str:
        return _validate_interval(value)

    @model_validator(mode="after")
    def _valid_snapshot(self) -> "BitunixCockpitSnapshot":
        if not self.candles:
            raise ValueError("cockpit snapshot requires candles")
        if not 0 <= self.opportunity_rating <= 100:
            raise ValueError("opportunity rating must be 0-100")
        if not 0 <= self.risk_rating <= 100:
            raise ValueError("risk rating must be 0-100")
        if not self.reason_codes:
            raise ValueError("snapshot requires reason codes")
        return self

    def chart_candles(self) -> list[dict[str, float | int]]:
        return [candle.chart_dict() for candle in self.candles]


BitunixResultValue: TypeAlias = (
    list[BitunixTicker]
    | list[BitunixCandle]
    | BitunixFundingRate
    | BitunixDepthSnapshot
    | BitunixCockpitSnapshot
)


class BitunixAdapterResult(BitunixBaseModel):
    status: Literal["OK", "INSUFFICIENT_DATA"]
    reason_codes: tuple[str, ...]
    value: BitunixResultValue | None = None

    @model_validator(mode="after")
    def _valid_result(self) -> "BitunixAdapterResult":
        if not self.reason_codes:
            raise ValueError("Bitunix adapter result requires reason codes")
        if self.status == "OK" and self.value is None:
            raise ValueError("OK Bitunix result requires value")
        if self.status != "OK" and self.value is not None:
            raise ValueError("INSUFFICIENT_DATA cannot carry value")
        return self

    @property
    def ok(self) -> bool:
        return self.status == "OK"

    @classmethod
    def success(cls, value: BitunixResultValue, *reason_codes: str) -> "BitunixAdapterResult":
        return cls(status="OK", reason_codes=tuple(reason_codes or ("BITUNIX_OK",)), value=value)

    @classmethod
    def insufficient(cls, *reason_codes: str) -> "BitunixAdapterResult":
        return cls(status="INSUFFICIENT_DATA", reason_codes=tuple(reason_codes or ("BITUNIX_INSUFFICIENT_DATA",)))


def parse_order_book_levels(raw_levels: Any) -> tuple[BitunixOrderBookLevel, ...]:
    if not isinstance(raw_levels, list):
        raise ValueError("order book side must be a list")
    return tuple(BitunixOrderBookLevel.from_raw(level) for level in raw_levels)


def validation_error_reason(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return "BITUNIX_VALIDATION_FAILED"
    return "BITUNIX_MALFORMED_DATA"


def _validate_symbol(value: str) -> str:
    normalized = value.upper().strip()
    if normalized not in BITUNIX_ALLOWED_SYMBOLS:
        raise ValueError("unsupported Bitunix symbol")
    return normalized


def _validate_interval(value: str) -> str:
    normalized = value.strip()
    if normalized not in BITUNIX_ALLOWED_INTERVALS:
        raise ValueError("unsupported Bitunix interval")
    return normalized


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value
