"""Read-only Bitunix public futures REST adapter."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import httpx
from pydantic import ValidationError

from data_pipeline.bitunix_models import (
    BITUNIX_ALLOWED_DEPTH_LIMITS,
    BITUNIX_ALLOWED_INTERVALS,
    BITUNIX_ALLOWED_SYMBOLS,
    BITUNIX_INTERVAL_SECONDS,
    BitunixAdapterResult,
    BitunixCandle,
    BitunixCockpitSnapshot,
    BitunixDepthSnapshot,
    BitunixFundingRate,
    BitunixTicker,
    parse_order_book_levels,
    validation_error_reason,
)

BITUNIX_FUTURES_BASE_URL = "https://fapi.bitunix.com"
PUBLIC_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "TRAIDR-bitunix-read-only",
}

Transport = Callable[[str, Mapping[str, str]], Mapping[str, Any] | Awaitable[Mapping[str, Any]]]


class BitunixFuturesAdapter:
    """Fetch public Bitunix futures market data without auth or execution."""

    def __init__(
        self,
        transport: Transport | None = None,
        *,
        base_url: str = BITUNIX_FUTURES_BASE_URL,
        timeout_seconds: float = 5.0,
        now: datetime | None = None,
    ) -> None:
        self.transport = transport
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.now = now

    async def fetch_tickers(self, symbols: tuple[str, ...]) -> BitunixAdapterResult:
        normalized = _normalize_symbols(symbols)
        if not normalized:
            return BitunixAdapterResult.insufficient("BITUNIX_UNSUPPORTED_SYMBOL")
        try:
            raw = await self._get_json(
                "/api/v1/futures/market/tickers",
                {"symbols": ",".join(normalized)},
            )
            data = _required_data(raw)
            if not isinstance(data, list) or not data:
                return BitunixAdapterResult.insufficient("BITUNIX_TICKERS_MISSING")
            observed_at = self._now()
            tickers = [
                BitunixTicker.model_validate({**_require_mapping(item), "observed_at": observed_at})
                for item in data
                if str(_require_mapping(item).get("symbol", "")).upper() in normalized
            ]
            if not tickers:
                return BitunixAdapterResult.insufficient("BITUNIX_TICKERS_MISSING")
            return BitunixAdapterResult.success(tickers, "BITUNIX_TICKERS_OK", "NO_EXECUTION_ACTION")
        except Exception as error:
            return _insufficient_from_error(error, "BITUNIX_TICKERS_FAILED")

    async def fetch_kline(self, symbol: str, interval: str, limit: int = 200) -> BitunixAdapterResult:
        normalized_symbol = _normalize_symbol(symbol)
        normalized_interval = _normalize_interval(interval)
        if normalized_symbol is None or normalized_interval is None:
            return BitunixAdapterResult.insufficient("BITUNIX_UNSUPPORTED_SYMBOL_OR_INTERVAL")
        if limit < 1 or limit > 200:
            return BitunixAdapterResult.insufficient("BITUNIX_INVALID_KLINE_LIMIT")
        try:
            raw = await self._get_json(
                "/api/v1/futures/market/kline",
                {
                    "symbol": normalized_symbol,
                    "interval": normalized_interval,
                    "limit": str(limit),
                    "type": "LAST_PRICE",
                },
            )
            data = _required_data(raw)
            if not isinstance(data, list) or not data:
                return BitunixAdapterResult.insufficient("BITUNIX_KLINE_MISSING")
            candles, malformed_count = _parse_valid_candles(data, normalized_symbol, normalized_interval)
            if len(candles) < 2:
                return BitunixAdapterResult.insufficient("BITUNIX_KLINE_INSUFFICIENT_VALID_CANDLES")
            if _candles_stale(candles, normalized_interval, self._now()):
                return BitunixAdapterResult.insufficient("BITUNIX_KLINE_STALE")
            reason_codes = ["BITUNIX_KLINE_OK", "NO_EXECUTION_ACTION"]
            if malformed_count:
                reason_codes.append("BITUNIX_KLINE_DROPPED_MALFORMED_CANDLES")
            return BitunixAdapterResult.success(list(candles), *tuple(reason_codes))
        except Exception as error:
            return _insufficient_from_error(error, "BITUNIX_KLINE_FAILED")

    async def fetch_funding_rate(self, symbol: str) -> BitunixAdapterResult:
        normalized_symbol = _normalize_symbol(symbol)
        if normalized_symbol is None:
            return BitunixAdapterResult.insufficient("BITUNIX_UNSUPPORTED_SYMBOL")
        try:
            raw = await self._get_json(
                "/api/v1/futures/market/funding_rate",
                {"symbol": normalized_symbol},
            )
            data = _required_data(raw)
            item = data[0] if isinstance(data, list) and data else data
            funding = BitunixFundingRate.model_validate(
                {**_require_mapping(item), "observed_at": self._now()}
            )
            return BitunixAdapterResult.success(funding, "BITUNIX_FUNDING_OK", "NO_EXECUTION_ACTION")
        except Exception as error:
            return _insufficient_from_error(error, "BITUNIX_FUNDING_FAILED")

    async def fetch_depth(self, symbol: str, limit: str = "15") -> BitunixAdapterResult:
        normalized_symbol = _normalize_symbol(symbol)
        normalized_limit = str(limit)
        if normalized_symbol is None or normalized_limit not in BITUNIX_ALLOWED_DEPTH_LIMITS:
            return BitunixAdapterResult.insufficient("BITUNIX_UNSUPPORTED_DEPTH_REQUEST")
        try:
            raw = await self._get_json(
                "/api/v1/futures/market/depth",
                {"symbol": normalized_symbol, "limit": normalized_limit},
            )
            data = _require_mapping(_required_data(raw))
            bids = parse_order_book_levels(data.get("bids", data.get("b")))
            asks = parse_order_book_levels(data.get("asks", data.get("a")))
            depth = BitunixDepthSnapshot(
                symbol=normalized_symbol,
                bids=bids,
                asks=asks,
                observed_at=self._now(),
            )
            depth.depth_delta()
            return BitunixAdapterResult.success(depth, "BITUNIX_DEPTH_OK", "NO_EXECUTION_ACTION")
        except Exception as error:
            return _insufficient_from_error(error, "BITUNIX_DEPTH_FAILED")

    async def fetch_cockpit_snapshot(
        self,
        symbol: str,
        interval: str,
        depth_limit: str = "15",
    ) -> BitunixAdapterResult:
        normalized_symbol = _normalize_symbol(symbol)
        normalized_interval = _normalize_interval(interval)
        if normalized_symbol is None or normalized_interval is None:
            return BitunixAdapterResult.insufficient("BITUNIX_UNSUPPORTED_SYMBOL_OR_INTERVAL")

        tickers_result = await self.fetch_tickers((normalized_symbol,))
        kline_result = await self.fetch_kline(normalized_symbol, normalized_interval)
        funding_result = await self.fetch_funding_rate(normalized_symbol)
        depth_result = await self.fetch_depth(normalized_symbol, depth_limit)
        failures = [
            reason
            for result in (tickers_result, kline_result, funding_result, depth_result)
            if not result.ok
            for reason in result.reason_codes
        ]
        if failures:
            return BitunixAdapterResult.insufficient("BITUNIX_COCKPIT_INSUFFICIENT", *tuple(dict.fromkeys(failures)))

        tickers = cast(list[BitunixTicker], tickers_result.value)
        candles = cast(list[BitunixCandle], kline_result.value)
        funding = cast(BitunixFundingRate, funding_result.value)
        depth = cast(BitunixDepthSnapshot, depth_result.value)
        depth_delta = depth.depth_delta()
        opportunity_rating = _opportunity_rating(candles, tickers[0], funding, depth_delta.depth_delta_percent)
        risk_rating = _risk_rating(candles, funding, depth_delta.depth_delta_percent, depth_delta.bid_sum + depth_delta.ask_sum)
        reason_codes = tuple(
            dict.fromkeys(
                (
                    "BITUNIX_PUBLIC_REST",
                    "BITUNIX_COCKPIT_OK",
                    "RESEARCH_ONLY",
                    "NO_EXECUTION_ACTION",
                    *tuple(kline_result.reason_codes),
                )
            )
        )
        snapshot = BitunixCockpitSnapshot(
            symbol=normalized_symbol,
            interval=normalized_interval,
            ticker=tickers[0],
            candles=tuple(candles),
            funding_rate=funding,
            depth=depth,
            depth_delta=depth_delta,
            opportunity_rating=opportunity_rating,
            risk_rating=risk_rating,
            reason_codes=reason_codes,
            observed_at=self._now(),
        )
        return BitunixAdapterResult.success(snapshot, "BITUNIX_COCKPIT_OK", "NO_EXECUTION_ACTION")

    async def _get_json(self, path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        if self.transport is not None:
            result = self.transport(path, params)
            if inspect.isawaitable(result):
                result = await result
            return _require_mapping(result)

        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            headers=PUBLIC_HEADERS,
        ) as client:
            response = await client.get(path, params=dict(params))
            response.raise_for_status()
            return _require_mapping(response.json())

    def _now(self) -> datetime:
        return self.now or datetime.now(tz=UTC)


def _normalize_symbol(symbol: str) -> str | None:
    normalized = symbol.upper().strip()
    return normalized if normalized in BITUNIX_ALLOWED_SYMBOLS else None


def _normalize_symbols(symbols: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(symbol for symbol in (_normalize_symbol(symbol) for symbol in symbols) if symbol)
    return tuple(dict.fromkeys(normalized))


def _normalize_interval(interval: str) -> str | None:
    normalized = interval.strip()
    return normalized if normalized in BITUNIX_ALLOWED_INTERVALS else None


def _required_data(raw: Mapping[str, Any]) -> Any:
    if raw.get("code") != 0:
        raise BitunixApiError("Bitunix API returned non-zero code")
    if "data" not in raw:
        raise ValueError("Bitunix response missing data")
    return raw["data"]


def _require_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("expected mapping")
    return value


def _parse_valid_candles(
    rows: list[Any],
    symbol: str,
    interval: str,
) -> tuple[tuple[BitunixCandle, ...], int]:
    candles: list[BitunixCandle] = []
    malformed_count = 0
    for item in rows:
        try:
            candles.append(
                BitunixCandle.model_validate(
                    {
                        **_require_mapping(item),
                        "symbol": symbol,
                        "interval": interval,
                    }
                )
            )
        except (ValidationError, ValueError, TypeError):
            malformed_count += 1
    return tuple(sorted(candles, key=lambda candle: candle.time_ms)), malformed_count


def _candles_stale(candles: tuple[BitunixCandle, ...], interval: str, now: datetime) -> bool:
    if not candles:
        return True
    latest = candles[-1].observed_at
    max_age_seconds = BITUNIX_INTERVAL_SECONDS[interval] * 3
    return (now - latest).total_seconds() > max_age_seconds


def _opportunity_rating(
    candles: list[BitunixCandle],
    ticker: BitunixTicker,
    funding: BitunixFundingRate,
    depth_delta_percent: Any,
) -> int:
    first_close = candles[0].close
    last_close = candles[-1].close
    trend_score = 30 if last_close > first_close else 15 if last_close == first_close else 5
    volume_score = 20 if ticker.quote_volume > 0 or sum(candle.quote_volume for candle in candles) > 0 else 0
    depth_value = float(depth_delta_percent)
    depth_score = max(0, int(25 - abs(depth_value - 55) * 0.8))
    funding_abs = abs(funding.funding_rate)
    funding_score = 15 if funding_abs <= 0.001 else 7 if funding_abs <= 0.01 else 0
    return max(0, min(100, trend_score + volume_score + depth_score + funding_score + 10))


def _risk_rating(
    candles: list[BitunixCandle],
    funding: BitunixFundingRate,
    depth_delta_percent: Any,
    total_depth_amount: Any,
) -> int:
    risk = 20
    if len(candles) < 25:
        risk += 15
    depth_value = float(depth_delta_percent)
    if depth_value < 20 or depth_value > 80:
        risk += 25
    if total_depth_amount < 1:
        risk += 20
    if abs(funding.funding_rate) > Decimal("0.01"):
        risk += 20
    return max(0, min(100, risk))


def _insufficient_from_error(error: Exception, fallback: str) -> BitunixAdapterResult:
    if isinstance(error, BitunixApiError):
        return BitunixAdapterResult.insufficient("BITUNIX_API_ERROR")
    if isinstance(error, (httpx.HTTPError, TimeoutError)):
        return BitunixAdapterResult.insufficient("BITUNIX_HTTP_FAILED")
    if isinstance(error, (ValidationError, ValueError, TypeError)):
        return BitunixAdapterResult.insufficient(validation_error_reason(error))
    return BitunixAdapterResult.insufficient(fallback)


class BitunixApiError(RuntimeError):
    """Raised when Bitunix returns an error envelope."""
