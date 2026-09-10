"""Read-only external market-data providers behind one async interface.

CoinGlass and CoinMarketCap are optional authenticated data sources. Their keys are
accepted only in memory, never persisted or emitted in provider results. CoinGecko
uses its keyless public API by default. Bitunix private account access is deliberately
represented only by a disabled boundary; this module contains no signing or private
exchange request implementation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
import hashlib
import re
import time
from typing import Any, cast

import httpx

from data_pipeline.bitunix_futures_adapter import BitunixFuturesAdapter
from data_pipeline.bitunix_models import BitunixCockpitSnapshot
from data_pipeline.provider_contracts import (
    ProviderCapability,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderHttpResponse,
    ProviderObservation,
    ProviderResult,
    ProviderTransport,
    TTLCache,
    normalize_timestamp,
)
from data_pipeline.provider_runtime import ProviderCircuitBreaker, TokenBucket, parse_retry_after


COINGLASS_BASE_URL = "https://open-api-v4.coinglass.com"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
COINMARKETCAP_BASE_URL = "https://pro-api.coinmarketcap.com"
COINMARKETCAP_KEYLESS_BASE_URL = f"{COINMARKETCAP_BASE_URL}/public-api"
CRYPTOPANIC_BASE_URL = "https://cryptopanic.com/api/v1"


class _JsonProvider:
    """Shared retry, rate-limit, circuit, cache and timestamp behavior."""

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        transport: ProviderTransport | None = None,
        headers: Mapping[str, str] | None = None,
        cache_ttl_seconds: float = 15.0,
        rate_per_second: float = 1.0,
        rate_capacity: int = 1,
        timeout_seconds: float = 10.0,
        maximum_attempts: int = 2,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.headers = {"Accept": "application/json", **dict(headers or {})}
        self.timeout_seconds = timeout_seconds
        self.maximum_attempts = max(1, maximum_attempts)
        self.sleep = sleep or asyncio.sleep
        self.bucket = TokenBucket(rate_per_second, rate_capacity)
        self.circuit = ProviderCircuitBreaker(name, "market")
        self.cache: TTLCache[ProviderObservation] = TTLCache(cache_ttl_seconds)
        self._last_health = ProviderHealth(
            provider=name,
            checked_at=datetime.now(tz=UTC),
            status=ProviderHealthStatus.INSUFFICIENT_DATA,
            latency_ms=None,
            clock_skew_ms=None,
            consecutive_failures=0,
            rate_limited=False,
            reason_codes=("PROVIDER_HEALTH_CHECK_NOT_RUN",),
        )

    async def _request(
        self,
        path: str,
        *,
        params: Mapping[str, str],
        headers: Mapping[str, str] | None = None,
    ) -> tuple[ProviderHttpResponse | None, tuple[str, ...]]:
        now = datetime.now(tz=UTC)
        if not self.circuit.allow(now):
            self._update_health(
                status=ProviderHealthStatus.DOWN,
                latency_ms=None,
                clock_skew_ms=None,
                rate_limited=False,
                reason_codes=("PROVIDER_CIRCUIT_OPEN",),
            )
            return None, ("PROVIDER_CIRCUIT_OPEN",)

        await self.bucket.acquire()
        request_headers = {**self.headers, **dict(headers or {})}
        url = f"{self.base_url}/{path.lstrip('/')}"
        reasons: list[str] = []
        for attempt in range(self.maximum_attempts):
            started = time.perf_counter()
            try:
                if self.transport is not None:
                    response = self.transport(url, params, request_headers)
                    if hasattr(response, "__await__"):
                        response = await cast(Awaitable[ProviderHttpResponse], response)
                    result = response
                else:
                    async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                        raw = await client.get(url, params=params, headers=request_headers)
                    try:
                        payload = raw.json()
                    except ValueError:
                        payload = None
                    result = ProviderHttpResponse(
                        status_code=raw.status_code,
                        payload=payload if isinstance(payload, (Mapping, list)) else None,
                        headers=dict(raw.headers),
                        received_at=datetime.now(tz=UTC),
                    )
            except (httpx.HTTPError, OSError, TimeoutError, ValueError):
                self.circuit.failure(now=now)
                reasons.append("PROVIDER_TRANSPORT_FAILED")
                self._update_health(
                    status=ProviderHealthStatus.DOWN,
                    latency_ms=(time.perf_counter() - started) * 1000.0,
                    clock_skew_ms=None,
                    rate_limited=False,
                    reason_codes=tuple(reasons),
                )
                return None, tuple(reasons)

            latency_ms = (time.perf_counter() - started) * 1000.0
            if result.status_code == 200:
                self.circuit.success()
                skew = _clock_skew_ms(result, now)
                self._update_health(
                    status=ProviderHealthStatus.HEALTHY,
                    latency_ms=latency_ms,
                    clock_skew_ms=skew,
                    rate_limited=False,
                    reason_codes=("PROVIDER_HTTP_OK",),
                )
                return result, tuple(dict.fromkeys((*reasons, "PROVIDER_HTTP_OK")))

            if result.status_code == 429:
                retry_after_seconds = parse_retry_after(_header_value(result.headers, "Retry-After"))
                self.circuit.failure(
                    retry_after_seconds=retry_after_seconds,
                    now=now,
                )
                reasons.append("PROVIDER_RATE_LIMITED")
                if attempt + 1 < self.maximum_attempts:
                    retry_after = retry_after_seconds or self.circuit.backoff_seconds(attempt)
                    await self.sleep(min(retry_after, 5.0))
                    continue
                self._update_health(
                    status=ProviderHealthStatus.DEGRADED,
                    latency_ms=latency_ms,
                    clock_skew_ms=None,
                    rate_limited=True,
                    reason_codes=tuple(reasons),
                )
                return result, tuple(reasons)

            self.circuit.failure(now=now)
            reason = "PROVIDER_AUTH_FAILED" if result.status_code in {401, 403} else "PROVIDER_HTTP_FAILED"
            reasons.append(reason)
            self._update_health(
                status=ProviderHealthStatus.DEGRADED,
                latency_ms=latency_ms,
                clock_skew_ms=_clock_skew_ms(result, now),
                rate_limited=False,
                reason_codes=tuple(reasons),
            )
            return result, tuple(reasons)

        return None, tuple(reasons or ("PROVIDER_REQUEST_FAILED",))

    def _update_health(
        self,
        *,
        status: ProviderHealthStatus,
        latency_ms: float | None,
        clock_skew_ms: float | None,
        rate_limited: bool,
        reason_codes: tuple[str, ...],
    ) -> None:
        previous_failures = self._last_health.consecutive_failures
        failures = 0 if status is ProviderHealthStatus.HEALTHY else previous_failures + 1
        self._last_health = ProviderHealth(
            provider=self.name,
            checked_at=datetime.now(tz=UTC),
            status=status,
            latency_ms=latency_ms,
            clock_skew_ms=clock_skew_ms,
            consecutive_failures=failures,
            rate_limited=rate_limited,
            reason_codes=reason_codes,
        )

    async def health_check(self, *, now: datetime | None = None) -> ProviderHealth:
        result, reasons = await self._request("ping", params={})
        if result is None or result.status_code != 200:
            return self._last_health
        reference = now or datetime.now(tz=UTC)
        self._update_health(
            status=ProviderHealthStatus.HEALTHY,
            latency_ms=self._last_health.latency_ms,
            clock_skew_ms=_clock_skew_ms(result, reference),
            rate_limited=False,
            reason_codes=("PROVIDER_HEALTHY", *reasons),
        )
        return self._last_health


class BitunixPublicProvider:
    """Unified REST snapshot facade over TRAIDR's existing Bitunix adapter."""

    name = "bitunix_public"
    capabilities = (
        ProviderCapability.CANDLES,
        ProviderCapability.ORDER_BOOK,
        ProviderCapability.TICKERS,
        ProviderCapability.FUNDING,
    )

    def __init__(
        self,
        adapter: BitunixFuturesAdapter | None = None,
        *,
        interval: str = "15m",
        depth_limit: str = "15",
    ) -> None:
        self.adapter = adapter or BitunixFuturesAdapter()
        self.interval = interval
        self.depth_limit = depth_limit
        self._last_health = ProviderHealth(
            provider=self.name,
            checked_at=datetime.now(tz=UTC),
            status=ProviderHealthStatus.INSUFFICIENT_DATA,
            latency_ms=None,
            clock_skew_ms=None,
            consecutive_failures=0,
            rate_limited=False,
            reason_codes=("PROVIDER_HEALTH_CHECK_NOT_RUN",),
        )

    async def fetch(
        self,
        instrument_id: str,
        *,
        now: datetime | None = None,
    ) -> ProviderResult[ProviderObservation]:
        symbol = instrument_id.split(":", 1)[-1].upper()
        started = time.perf_counter()
        result = await self.adapter.fetch_cockpit_snapshot(symbol, self.interval, self.depth_limit)
        latency = (time.perf_counter() - started) * 1000.0
        if not result.ok or result.value is None:
            self._last_health = ProviderHealth(
                provider=self.name,
                checked_at=datetime.now(tz=UTC),
                status=ProviderHealthStatus.DEGRADED,
                latency_ms=latency,
                clock_skew_ms=None,
                consecutive_failures=self._last_health.consecutive_failures + 1,
                rate_limited=False,
                reason_codes=result.reason_codes,
            )
            return ProviderResult.insufficient(self.name, self._last_health, *result.reason_codes)
        snapshot = cast(BitunixCockpitSnapshot, result.value)
        fields = _bitunix_fields(snapshot)
        observation = ProviderObservation(
            provider=self.name,
            instrument_id=instrument_id,
            observed_at=snapshot.observed_at,
            received_at=datetime.now(tz=UTC),
            fields=fields,
            capabilities=self.capabilities,
            metadata={"symbol": snapshot.symbol, "interval": snapshot.interval},
            reason_codes=("BITUNIX_PUBLIC_REST", "NO_EXECUTION_ACTION"),
        )
        self._last_health = ProviderHealth(
            provider=self.name,
            checked_at=datetime.now(tz=UTC),
            status=ProviderHealthStatus.HEALTHY,
            latency_ms=latency,
            clock_skew_ms=(datetime.now(tz=UTC) - snapshot.observed_at).total_seconds() * 1000.0,
            consecutive_failures=0,
            rate_limited=False,
            reason_codes=("BITUNIX_PUBLIC_HEALTHY",),
        )
        return ProviderResult(
            provider=self.name,
            status=ProviderHealthStatus.HEALTHY,
            value=observation,
            health=self._last_health,
            reason_codes=observation.reason_codes,
        )

    async def health_check(self, *, now: datetime | None = None) -> ProviderHealth:
        return self._last_health


class CoinGlassProvider(_JsonProvider):
    """CoinGlass V4 derivatives context provider; key is optional at construction only."""

    capabilities = (
        ProviderCapability.FUNDING,
        ProviderCapability.OPEN_INTEREST,
        ProviderCapability.LIQUIDATIONS,
        ProviderCapability.LONG_SHORT,
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: ProviderTransport | None = None,
        cache_ttl_seconds: float = 30.0,
    ) -> None:
        headers = {"CG-API-KEY": api_key} if api_key else {}
        super().__init__(
            name="coinglass",
            base_url=COINGLASS_BASE_URL,
            transport=transport,
            headers=headers,
            cache_ttl_seconds=cache_ttl_seconds,
            rate_per_second=1.0,
            rate_capacity=1,
        )
        self.shadow_cache: TTLCache[ProviderObservation] = TTLCache(max(cache_ttl_seconds, 120.0))

    async def fetch(
        self,
        instrument_id: str,
        *,
        now: datetime | None = None,
        _shadow: bool = False,
    ) -> ProviderResult[ProviderObservation]:
        symbol = _asset_symbol(instrument_id)
        cache_key = f"{self.name}:{'shadow:' if _shadow else ''}{symbol}"
        selected_cache = self.shadow_cache if _shadow else self.cache
        cached = selected_cache.get(cache_key, now=now)
        if cached is not None:
            return ProviderResult(
                provider=self.name,
                status=ProviderHealthStatus.HEALTHY,
                value=cached,
                health=self._last_health,
                reason_codes=("PROVIDER_CACHE_HIT",),
            )
        if not self.headers.get("CG-API-KEY"):
            return ProviderResult.insufficient(
                self.name,
                self._missing_key_health("COINGLASS_API_KEY_MISSING"),
                "COINGLASS_API_KEY_MISSING",
            )

        base_observation: ProviderObservation | None = None
        base_reasons: tuple[str, ...] = ()
        if _shadow:
            core_result = await self.fetch(instrument_id, now=now)
            if not core_result.ok or core_result.value is None:
                return ProviderResult.insufficient(
                    self.name,
                    core_result.health,
                    *core_result.reason_codes,
                    "COINGLASS_SHADOW_CORE_UNAVAILABLE",
                )
            base_observation = core_result.value
            base_reasons = core_result.reason_codes

        expanded_requests = (
            ("funding_rate", "/api/futures/funding-rate/history", {"symbol": symbol, "interval": "h1", "limit": "2"}),
            ("funding_oi_weighted", "/api/futures/funding-rate/oi-weight-history", {"symbol": symbol, "interval": "h1", "limit": "2"}),
            ("funding_volume_weighted", "/api/futures/funding-rate/vol-weight-history", {"symbol": symbol, "interval": "h1", "limit": "2"}),
            ("oi_5m", "/api/futures/open-interest/aggregated-history", {"symbol": symbol, "interval": "m5", "limit": "2"}),
            ("oi_15m", "/api/futures/open-interest/aggregated-history", {"symbol": symbol, "interval": "m15", "limit": "2"}),
            ("oi_1h", "/api/futures/open-interest/aggregated-history", {"symbol": symbol, "interval": "h1", "limit": "2"}),
            ("oi_4h", "/api/futures/open-interest/aggregated-history", {"symbol": symbol, "interval": "h4", "limit": "2"}),
            ("liquidations", "/api/futures/liquidation/aggregated-history", {"symbol": symbol, "interval": "h1", "limit": "2"}),
            ("long_short", "/api/futures/global-long-short-account-ratio/history", {"symbol": symbol, "interval": "h1", "limit": "2"}),
            ("top_long_short", "/api/futures/top-long-short-position-ratio/history", {"symbol": symbol, "interval": "h1", "limit": "2"}),
            ("taker_flow", "/api/futures/taker-buy-sell-volume/exchange-list", {"symbol": symbol}),
            ("crowding", "/api/futures/coins-markets", {"symbol": symbol}),
        )
        core_kinds = {"funding_rate", "oi_1h", "liquidations", "long_short"}
        requests = tuple(
            request
            for request in expanded_requests
            if (request[0] not in core_kinds if _shadow else request[0] in core_kinds)
        )
        responses = await asyncio.gather(
            *(
                self._request(path, params=params)
                for _, path, params in requests
            )
        )
        fields: dict[str, float] = dict(base_observation.fields) if base_observation is not None else {}
        reasons: list[str] = list(base_reasons)
        observed_times: list[datetime] = [base_observation.observed_at] if base_observation is not None else []
        for (kind, _, _), (response, response_reasons) in zip(requests, responses, strict=True):
            reasons.extend(f"COINGLASS_{kind.upper()}_{reason}" for reason in response_reasons)
            if response is None:
                continue
            record = _latest_record(response.payload)
            if record is None:
                reasons.append(f"COINGLASS_{kind.upper()}_MISSING")
                continue
            observed = _record_time(record, response.received_at)
            if observed is not None:
                observed_times.append(observed)
            if kind in {"funding_rate", "funding_oi_weighted", "funding_volume_weighted"}:
                value = _number(record, "funding_rate", "fundingRate", "rate", "value")
                if value is not None:
                    target = {
                        "funding_rate": "funding_rate",
                        "funding_oi_weighted": "funding_oi_weighted",
                        "funding_volume_weighted": "funding_volume_weighted",
                    }[kind]
                    fields[target] = value
            elif kind.startswith("oi_"):
                value = _number(record, "open_interest", "openInterest", "oi", "value")
                change = _number(
                    record,
                    "oi_change_pct",
                    "openInterestChangePercent",
                    "open_interest_change_percent",
                    "changePercent",
                    "change",
                )
                if change is None:
                    change = _record_percent_change(response.payload, "open_interest", "openInterest", "oi", "value")
                if value is not None:
                    fields["open_interest"] = value
                if change is not None:
                    horizon = kind.removeprefix("oi_")
                    fields[f"oi_change_pct_{horizon}"] = change
                    if horizon == "1h":
                        fields["oi_change_pct"] = change
            elif kind == "liquidations":
                long_value = _number(record, "long_liquidation", "longLiquidation", "longLiquidationUsd")
                short_value = _number(record, "short_liquidation", "shortLiquidation", "shortLiquidationUsd")
                if long_value is not None and short_value is not None and long_value + short_value > 0:
                    fields["liquidation_pressure"] = (long_value - short_value) / (long_value + short_value)
                    fields["liquidation_total_usd"] = long_value + short_value
                    acceleration = _liquidation_acceleration(response.payload)
                    if acceleration is not None:
                        fields["liquidation_acceleration_pct"] = acceleration
            elif kind in {"long_short", "top_long_short"}:
                value = _number(record, "long_short_ratio", "longShortRatio", "ratio", "value")
                if value is not None:
                    fields["long_short_ratio" if kind == "long_short" else "top_long_short_ratio"] = value
            elif kind == "taker_flow":
                buy = _number(record, "buy_volume", "buyVolume", "takerBuyVolume")
                sell = _number(record, "sell_volume", "sellVolume", "takerSellVolume")
                if buy is not None and sell is not None and buy + sell > 0:
                    fields["taker_buy_sell_imbalance"] = (buy - sell) / (buy + sell)
            elif kind == "crowding":
                fields.update(
                    _optional_numbers(
                        {
                            "oi_market_cap_ratio": record.get("open_interest_market_cap_ratio"),
                            "oi_volume_ratio": record.get("open_interest_volume_ratio"),
                            "long_short_ratio_5m": record.get("long_short_ratio_5m"),
                        }
                    )
                )

        if not fields:
            health = self._last_health
            return ProviderResult.insufficient(
                self.name,
                health,
                *tuple(dict.fromkeys((*reasons, "COINGLASS_NO_USABLE_METRICS"))),
            )
        # Composite evidence is only as fresh as its oldest contributing metric.
        observed_at = min(observed_times, default=datetime.now(tz=UTC))
        observation = ProviderObservation(
            provider=self.name,
            instrument_id=instrument_id,
            observed_at=observed_at,
            received_at=datetime.now(tz=UTC),
            fields=fields,
            capabilities=(
                (*self.capabilities, ProviderCapability.TAKER_FLOW, ProviderCapability.CROWDING)
                if _shadow
                else self.capabilities
            ),
            metadata={"symbol": symbol, "api_version": "v4", "shadow_fields": str(_shadow).lower()},
            reason_codes=tuple(
                dict.fromkeys(
                    (*reasons, "COINGLASS_READ_ONLY", *(("SHADOW_FEATURES_ZERO_WEIGHT",) if _shadow else ()))
                )
            ),
        )
        selected_cache.set(cache_key, observation, now=now)
        return ProviderResult(
            provider=self.name,
            status=ProviderHealthStatus.HEALTHY,
            value=observation,
            health=self._last_health,
            reason_codes=observation.reason_codes,
        )

    async def fetch_shadow(
        self,
        instrument_id: str,
        *,
        now: datetime | None = None,
    ) -> ProviderResult[ProviderObservation]:
        """Collect expanded derivatives evidence without entering the scoring path."""

        return await self.fetch(instrument_id, now=now, _shadow=True)

    def _missing_key_health(self, reason: str) -> ProviderHealth:
        health = ProviderHealth(
            provider=self.name,
            checked_at=datetime.now(tz=UTC),
            status=ProviderHealthStatus.INSUFFICIENT_DATA,
            latency_ms=None,
            clock_skew_ms=None,
            consecutive_failures=0,
            rate_limited=False,
            reason_codes=(reason,),
        )
        self._last_health = health
        return health


class CoinGeckoProvider(_JsonProvider):
    """CoinGecko keyless current, historical and metadata provider."""

    capabilities = (
        ProviderCapability.MARKET_DATA,
        ProviderCapability.METADATA,
    )

    def __init__(
        self,
        *,
        coin_ids: Mapping[str, str],
        transport: ProviderTransport | None = None,
        cache_ttl_seconds: float = 30.0,
    ) -> None:
        super().__init__(
            name="coingecko",
            base_url=COINGECKO_BASE_URL,
            transport=transport,
            cache_ttl_seconds=cache_ttl_seconds,
            rate_per_second=0.4,
            rate_capacity=1,
        )
        self.coin_ids = {key.upper(): value for key, value in coin_ids.items()}

    async def fetch(
        self,
        instrument_id: str,
        *,
        now: datetime | None = None,
    ) -> ProviderResult[ProviderObservation]:
        coin_id = self._coin_id(instrument_id)
        if coin_id is None:
            return ProviderResult.insufficient(
                self.name,
                self._missing_key_health("COINGECKO_EXACT_ID_MAPPING_MISSING"),
                "COINGECKO_EXACT_ID_MAPPING_MISSING",
            )
        cache_key = f"{self.name}:coin:{coin_id}"
        cached = self.cache.get(cache_key, now=now)
        if cached is not None:
            return ProviderResult(
                provider=self.name,
                status=ProviderHealthStatus.HEALTHY,
                value=cached,
                health=self._last_health,
                reason_codes=("PROVIDER_CACHE_HIT",),
            )
        response, reasons = await self._request(
            f"/coins/{coin_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false",
            },
        )
        if response is None or not isinstance(response.payload, Mapping):
            return ProviderResult.insufficient(self.name, self._last_health, *reasons)
        raw = response.payload
        market_data = _mapping(raw.get("market_data"))
        current = _mapping(market_data.get("current_price"))
        volume = _mapping(market_data.get("total_volume"))
        market_cap = _mapping(market_data.get("market_cap"))
        fields = _optional_numbers(
            {
                "price_usd": current.get("usd"),
                "volume_24h_usd": volume.get("usd"),
                "market_cap": market_cap.get("usd"),
                "price_change_24h": market_data.get("price_change_percentage_24h"),
            }
        )
        if not fields:
            return ProviderResult.insufficient(self.name, self._last_health, "COINGECKO_MARKET_DATA_MISSING")
        observed_at = normalize_timestamp(raw.get("last_updated"), received_at=response.received_at)
        if observed_at is None:
            observed_at = response.received_at
            reasons = (*reasons, "COINGECKO_TIMESTAMP_MISSING")
        observation = ProviderObservation(
            provider=self.name,
            instrument_id=instrument_id,
            observed_at=observed_at,
            received_at=response.received_at,
            fields=fields,
            capabilities=self.capabilities,
            metadata={
                "coin_id": coin_id,
                "name": str(raw.get("name", "")),
                "symbol": str(raw.get("symbol", "")).upper(),
                "asset_platform_id": str(raw.get("asset_platform_id", "")),
            },
            reason_codes=("COINGECKO_KEYLESS_PUBLIC", *reasons),
        )
        self.cache.set(cache_key, observation, now=now)
        return ProviderResult(
            provider=self.name,
            status=ProviderHealthStatus.HEALTHY,
            value=observation,
            health=self._last_health,
            reason_codes=observation.reason_codes,
        )

    async def fetch_history(
        self,
        instrument_id: str,
        *,
        days: int = 30,
        now: datetime | None = None,
    ) -> ProviderResult[tuple[Mapping[str, Any], ...]]:
        coin_id = self._coin_id(instrument_id)
        if coin_id is None or days < 1 or days > 365:
            return ProviderResult.insufficient(
                self.name,
                self._last_health,
                "COINGECKO_HISTORY_REQUEST_INVALID",
            )
        response, reasons = await self._request(
            f"/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": str(days), "interval": "daily"},
        )
        if response is None or not isinstance(response.payload, Mapping):
            return ProviderResult.insufficient(self.name, self._last_health, *reasons)
        prices = response.payload.get("prices")
        if not isinstance(prices, list):
            return ProviderResult.insufficient(self.name, self._last_health, "COINGECKO_HISTORY_MISSING")
        rows = tuple(
            {"timestamp_ms": row[0], "price_usd": row[1]}
            for row in prices
            if isinstance(row, list) and len(row) >= 2
        )
        if not rows:
            return ProviderResult.insufficient(self.name, self._last_health, "COINGECKO_HISTORY_EMPTY")
        return ProviderResult(
            provider=self.name,
            status=ProviderHealthStatus.HEALTHY,
            value=rows,
            health=self._last_health,
            reason_codes=("COINGECKO_HISTORY_OK",),
        )

    def _coin_id(self, instrument_id: str) -> str | None:
        symbol = instrument_id.split(":", 1)[-1].replace("USDT", "").upper()
        return self.coin_ids.get(instrument_id.upper()) or self.coin_ids.get(symbol)

    def _missing_key_health(self, reason: str) -> ProviderHealth:
        health = ProviderHealth(
            provider=self.name,
            checked_at=datetime.now(tz=UTC),
            status=ProviderHealthStatus.INSUFFICIENT_DATA,
            latency_ms=None,
            clock_skew_ms=None,
            consecutive_failures=0,
            rate_limited=False,
            reason_codes=(reason,),
        )
        self._last_health = health
        return health


class CoinMarketCapProvider(_JsonProvider):
    """CoinMarketCap rankings, quotes, trends and optional content context."""

    capabilities = (
        ProviderCapability.MARKET_DATA,
        ProviderCapability.METADATA,
        ProviderCapability.NEWS,
        ProviderCapability.EVENTS,
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: ProviderTransport | None = None,
        cache_ttl_seconds: float = 60.0,
    ) -> None:
        self.api_key = api_key.strip() if api_key else None
        base_url = COINMARKETCAP_BASE_URL if self.api_key else COINMARKETCAP_KEYLESS_BASE_URL
        headers = {"X-CMC_PRO_API_KEY": self.api_key} if self.api_key else {}
        super().__init__(
            name="coinmarketcap",
            base_url=base_url,
            transport=transport,
            headers=headers,
            cache_ttl_seconds=cache_ttl_seconds,
            rate_per_second=0.5,
            rate_capacity=1,
        )

    async def fetch(
        self,
        instrument_id: str,
        *,
        now: datetime | None = None,
    ) -> ProviderResult[ProviderObservation]:
        symbol = _asset_symbol(instrument_id)
        cache_key = f"{self.name}:quote:{symbol}"
        cached = self.cache.get(cache_key, now=now)
        if cached is not None:
            return ProviderResult(
                provider=self.name,
                status=ProviderHealthStatus.HEALTHY,
                value=cached,
                health=self._last_health,
                reason_codes=("PROVIDER_CACHE_HIT",),
            )
        response, reasons = await self._request(
            "/v3/cryptocurrency/quotes/latest",
            params={"symbol": symbol, "convert": "USD"},
        )
        record = _cmc_asset_record(response.payload if response else None, symbol)
        if record is None:
            return ProviderResult.insufficient(self.name, self._last_health, *reasons, "CMC_QUOTE_MISSING")
        quote = _mapping(_mapping(record.get("quote")).get("USD"))
        fields = _optional_numbers(
            {
                "price_usd": quote.get("price"),
                "volume_24h_usd": quote.get("volume_24h"),
                "market_cap": quote.get("market_cap"),
                "price_change_24h": quote.get("percent_change_24h"),
                "price_change_7d": quote.get("percent_change_7d"),
                "market_cap_rank": record.get("cmc_rank"),
            }
        )
        observed_at = normalize_timestamp(
            quote.get("last_updated") or record.get("last_updated"),
            received_at=response.received_at if response else None,
        ) or (response.received_at if response else datetime.now(tz=UTC))
        observation = ProviderObservation(
            provider=self.name,
            instrument_id=instrument_id,
            observed_at=observed_at,
            received_at=response.received_at if response else datetime.now(tz=UTC),
            fields=fields,
            capabilities=self.capabilities,
            metadata={
                "symbol": symbol,
                "cmc_id": str(record.get("id", "")),
                "name": str(record.get("name", "")),
                "slug": str(record.get("slug", "")),
                "api_mode": "authenticated" if self.api_key else "keyless",
            },
            reason_codes=("COINMARKETCAP_READ_ONLY", *reasons),
        )
        self.cache.set(cache_key, observation, now=now)
        return ProviderResult(
            provider=self.name,
            status=ProviderHealthStatus.HEALTHY,
            value=observation,
            health=self._last_health,
            reason_codes=observation.reason_codes,
        )

    async def fetch_rankings(
        self,
        *,
        limit: int = 100,
        now: datetime | None = None,
    ) -> ProviderResult[tuple[ProviderObservation, ...]]:
        if limit < 1 or limit > 1000:
            return ProviderResult.insufficient(self.name, self._last_health, "CMC_RANKING_LIMIT_INVALID")
        response, reasons = await self._request(
            "/v3/cryptocurrency/listings/latest",
            params={"start": "1", "limit": str(limit), "convert": "USD"},
        )
        rows = (response.payload.get("data") if response is not None and isinstance(response.payload, Mapping) else None)
        if not isinstance(rows, list):
            return ProviderResult.insufficient(self.name, self._last_health, *reasons, "CMC_RANKINGS_MISSING")
        observations = tuple(
            item
            for row in rows
            if isinstance(row, Mapping)
            for item in (self._observation_from_record(row, now=now),)
            if item is not None
        )
        if not observations:
            return ProviderResult.insufficient(self.name, self._last_health, "CMC_RANKINGS_EMPTY")
        return ProviderResult(
            provider=self.name,
            status=ProviderHealthStatus.HEALTHY,
            value=observations,
            health=self._last_health,
            reason_codes=("CMC_RANKINGS_OK", *reasons),
        )

    async def fetch_trending(
        self,
        *,
        limit: int = 50,
        now: datetime | None = None,
    ) -> ProviderResult[tuple[ProviderObservation, ...]]:
        if not self.api_key:
            return ProviderResult.insufficient(self.name, self._last_health, "CMC_TRENDING_API_KEY_REQUIRED")
        response, reasons = await self._request(
            "/v1/cryptocurrency/trending/latest",
            params={"start": "1", "limit": str(max(1, min(limit, 1000))), "convert": "USD"},
        )
        rows = (response.payload.get("data") if response is not None and isinstance(response.payload, Mapping) else None)
        if not isinstance(rows, list):
            return ProviderResult.insufficient(self.name, self._last_health, *reasons, "CMC_TRENDING_MISSING")
        observations = tuple(
            item
            for row in rows
            if isinstance(row, Mapping)
            for item in (self._observation_from_record(row, now=now),)
            if item is not None
        )
        return ProviderResult(
            provider=self.name,
            status=ProviderHealthStatus.HEALTHY if observations else ProviderHealthStatus.INSUFFICIENT_DATA,
            value=observations if observations else None,
            health=self._last_health,
            reason_codes=("CMC_TRENDING_OK", *reasons) if observations else ("CMC_TRENDING_EMPTY",),
        )

    async def fetch_content(
        self,
        *,
        symbol: str | None = None,
        limit: int = 20,
        now: datetime | None = None,
    ) -> ProviderResult[tuple[Mapping[str, Any], ...]]:
        if not self.api_key:
            return ProviderResult.insufficient(self.name, self._last_health, "CMC_CONTENT_API_KEY_REQUIRED")
        params = {"limit": str(max(1, min(limit, 200))), "language": "en"}
        if symbol:
            params["symbol"] = symbol.upper()
        response, reasons = await self._request("/v1/content/latest", params=params)
        rows = (response.payload.get("data") if response is not None and isinstance(response.payload, Mapping) else None)
        if not isinstance(rows, list):
            return ProviderResult.insufficient(self.name, self._last_health, *reasons, "CMC_CONTENT_MISSING")
        values = tuple(row for row in rows if isinstance(row, Mapping))
        return ProviderResult(
            provider=self.name,
            status=ProviderHealthStatus.HEALTHY if values else ProviderHealthStatus.INSUFFICIENT_DATA,
            value=values if values else None,
            health=self._last_health,
            reason_codes=("CMC_CONTENT_OK", *reasons) if values else ("CMC_CONTENT_EMPTY",),
        )

    async def fetch_technical_indicators(
        self,
        symbol: str,
        *,
        now: datetime | None = None,
    ) -> ProviderResult[Mapping[str, Any]]:
        """Keep indicator provenance explicit when CMC does not expose a documented route."""

        del symbol
        return ProviderResult.insufficient(
            self.name,
            self._last_health,
            "CMC_TECHNICAL_INDICATORS_API_UNAVAILABLE",
            "USE_TRAIDR_DETERMINISTIC_TECHNICALS",
        )

    async def fetch_events(self, *, now: datetime | None = None) -> ProviderResult[tuple[Mapping[str, Any], ...]]:
        """The public CMC API has no documented event-calendar endpoint; stay explicit."""

        return ProviderResult.insufficient(
            self.name,
            self._last_health,
            "CMC_EVENTS_API_UNAVAILABLE",
            "USE_CMC_EVENT_CALENDAR_OUTSIDE_TRAIDR_API",
        )

    def _observation_from_record(
        self,
        record: Mapping[str, Any],
        *,
        now: datetime | None,
    ) -> ProviderObservation | None:
        symbol = str(record.get("symbol") or "").upper()
        if not symbol:
            return None
        quote = _mapping(_mapping(record.get("quote")).get("USD"))
        fields = _optional_numbers(
            {
                "price_usd": quote.get("price"),
                "volume_24h_usd": quote.get("volume_24h"),
                "market_cap": quote.get("market_cap"),
                "price_change_24h": quote.get("percent_change_24h"),
                "market_cap_rank": record.get("cmc_rank"),
            }
        )
        received = now or datetime.now(tz=UTC)
        observed = normalize_timestamp(record.get("last_updated"), received_at=received) or received
        return ProviderObservation(
            provider=self.name,
            instrument_id=symbol,
            observed_at=observed,
            received_at=received,
            fields=fields,
            capabilities=self.capabilities,
            metadata={"symbol": symbol, "cmc_id": str(record.get("id", ""))},
            reason_codes=("CMC_RANKING_OBSERVATION",),
        )


class CryptoPanicProvider(_JsonProvider):
    """Deduplicated catalyst context that has no directional authority."""

    capabilities = (ProviderCapability.NEWS, ProviderCapability.EVENTS)

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: ProviderTransport | None = None,
        cache_ttl_seconds: float = 300.0,
    ) -> None:
        self.api_key = api_key.strip() if api_key else None
        super().__init__(
            name="cryptopanic",
            base_url=CRYPTOPANIC_BASE_URL,
            transport=transport,
            cache_ttl_seconds=cache_ttl_seconds,
            rate_per_second=0.2,
            rate_capacity=1,
        )

    async def fetch(
        self,
        instrument_id: str,
        *,
        now: datetime | None = None,
    ) -> ProviderResult[ProviderObservation]:
        symbol = _asset_symbol(instrument_id)
        cache_key = f"{self.name}:news:{symbol}"
        cached = self.cache.get(cache_key, now=now)
        if cached is not None:
            return ProviderResult(
                provider=self.name,
                status=ProviderHealthStatus.HEALTHY,
                value=cached,
                health=self._last_health,
                reason_codes=("PROVIDER_CACHE_HIT",),
            )
        if not self.api_key:
            return ProviderResult.insufficient(
                self.name,
                self._missing_key_health("CRYPTOPANIC_API_KEY_MISSING"),
                "CRYPTOPANIC_API_KEY_MISSING",
            )
        response, reasons = await self._request(
            "/posts/",
            params={
                "auth_token": self.api_key,
                "currencies": symbol,
                "kind": "news",
                "public": "true",
            },
        )
        items = _cryptopanic_items(
            response.payload if response else None,
            received_at=response.received_at if response else None,
        )
        if not items:
            return ProviderResult.insufficient(
                self.name,
                self._last_health,
                *reasons,
                "CRYPTOPANIC_NEWS_UNAVAILABLE",
            )
        latest = max(item["published_at"] for item in items)
        unique_sources = {str(item["source"]) for item in items}
        source_count = max(len(unique_sources), max(int(item["source_count"]) for item in items))
        average_novelty = sum(float(item["novelty"]) for item in items) / len(items)
        maximum_importance = max(float(item["importance"]) for item in items)
        observation = ProviderObservation(
            provider=self.name,
            instrument_id=instrument_id,
            observed_at=latest,
            received_at=response.received_at if response else datetime.now(tz=UTC),
            fields={
                "news_event_count": float(len(items)),
                "news_source_count": float(source_count),
                "news_importance": maximum_importance,
                "news_novelty": average_novelty,
                "news_corroboration": min(1.0, source_count / 3.0),
            },
            capabilities=self.capabilities,
            metadata={
                "symbol": symbol,
                "shadow_only": "true",
                "directional_authority": "none",
                "deduplicated_items": str(len(items)),
            },
            reason_codes=("CRYPTOPANIC_CONTEXT_ONLY", "NEWS_CANNOT_CREATE_DIRECTION", *reasons),
        )
        self.cache.set(cache_key, observation, now=now)
        return ProviderResult(
            provider=self.name,
            status=ProviderHealthStatus.HEALTHY,
            value=observation,
            health=self._last_health,
            reason_codes=observation.reason_codes,
        )

    def _missing_key_health(self, reason: str) -> ProviderHealth:
        health = ProviderHealth(
            provider=self.name,
            checked_at=datetime.now(tz=UTC),
            status=ProviderHealthStatus.INSUFFICIENT_DATA,
            latency_ms=None,
            clock_skew_ms=None,
            consecutive_failures=0,
            rate_limited=False,
            reason_codes=(reason,),
        )
        self._last_health = health
        return health


class BitunixPrivateReadOnlyBoundary:
    """Reserved future account-read boundary; no private request path is implemented."""

    name = "bitunix_private_read_only"
    capabilities: tuple[ProviderCapability, ...] = ()

    async def fetch(
        self,
        instrument_id: str,
        *,
        now: datetime | None = None,
    ) -> ProviderResult[ProviderObservation]:
        health = ProviderHealth(
            provider=self.name,
            checked_at=now or datetime.now(tz=UTC),
            status=ProviderHealthStatus.INSUFFICIENT_DATA,
            latency_ms=None,
            clock_skew_ms=None,
            consecutive_failures=0,
            rate_limited=False,
            reason_codes=("BITUNIX_PRIVATE_READ_ONLY_DEFERRED",),
        )
        return ProviderResult.insufficient(
            self.name,
            health,
            "BITUNIX_PRIVATE_READ_ONLY_DEFERRED",
            "NO_PRIVATE_ENDPOINTS_ENABLED",
        )

    async def health_check(self, *, now: datetime | None = None) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            checked_at=now or datetime.now(tz=UTC),
            status=ProviderHealthStatus.INSUFFICIENT_DATA,
            latency_ms=None,
            clock_skew_ms=None,
            consecutive_failures=0,
            rate_limited=False,
            reason_codes=("BITUNIX_PRIVATE_BOUNDARY_DISABLED",),
        )

    async def fetch_account_balance(self) -> ProviderResult[Mapping[str, Any]]:
        return self._disabled_result("BITUNIX_BALANCE_READ_DEFERRED")

    async def fetch_positions(self) -> ProviderResult[tuple[Mapping[str, Any], ...]]:
        return self._disabled_result("BITUNIX_POSITIONS_READ_DEFERRED")

    async def fetch_leverage(self) -> ProviderResult[Mapping[str, Any]]:
        return self._disabled_result("BITUNIX_LEVERAGE_READ_DEFERRED")

    async def fetch_protection_orders(self) -> ProviderResult[tuple[Mapping[str, Any], ...]]:
        return self._disabled_result("BITUNIX_TP_SL_READ_DEFERRED")

    def _disabled_result(self, reason: str) -> ProviderResult[Any]:
        health = ProviderHealth(
            provider=self.name,
            checked_at=datetime.now(tz=UTC),
            status=ProviderHealthStatus.INSUFFICIENT_DATA,
            latency_ms=None,
            clock_skew_ms=None,
            consecutive_failures=0,
            rate_limited=False,
            reason_codes=(reason, "NO_TRADING_OR_WITHDRAWAL_CAPABILITY"),
        )
        return ProviderResult.insufficient(self.name, health, reason, "NO_TRADING_OR_WITHDRAWAL_CAPABILITY")


def _bitunix_fields(snapshot: BitunixCockpitSnapshot) -> dict[str, float]:
    last = float(snapshot.ticker.last_price)
    open_price = float(snapshot.ticker.open_price)
    depth_percent = float(snapshot.depth_delta.depth_delta_percent)
    candles = snapshot.candles
    first_close = float(candles[0].close)
    last_close = float(candles[-1].close)
    return {
        "price_usd": last,
        "mark_price": float(snapshot.ticker.mark_price),
        "index_price": float(snapshot.funding_rate.index_price),
        "funding_rate": float(snapshot.funding_rate.funding_rate),
        "volume_24h_usd": float(snapshot.ticker.quote_volume),
        "price_change_24h": ((last - open_price) / open_price * 100.0) if open_price else 0.0,
        "price_structure": (last_close - first_close) / first_close if first_close else 0.0,
        "order_book_imbalance": (depth_percent - 50.0) / 50.0,
        "spread_bps": _spread_bps(snapshot),
    }


def _spread_bps(snapshot: BitunixCockpitSnapshot) -> float:
    bid = snapshot.depth.bids[0].price
    ask = snapshot.depth.asks[0].price
    midpoint = (bid + ask) / 2
    return float((ask - bid) / midpoint * 10_000) if midpoint > 0 else 0.0


def _asset_symbol(instrument_id: str) -> str:
    value = instrument_id.split(":", 1)[-1].upper()
    return value.removesuffix("USDT").removesuffix("USD")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_numbers(values: Mapping[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, value in values.items():
        try:
            if value is not None:
                result[key] = float(value)
        except (TypeError, ValueError):
            continue
    return result


def _records(payload: Mapping[str, Any] | list[Any] | None) -> tuple[Mapping[str, Any], ...]:
    if isinstance(payload, Mapping):
        data = payload.get("data", payload)
        if isinstance(data, Mapping):
            for key in ("list", "data", "items", "rows", "result"):
                nested = data.get(key)
                if isinstance(nested, list):
                    return tuple(item for item in nested if isinstance(item, Mapping))
            return (data,)
        if isinstance(data, list):
            return tuple(item for item in data if isinstance(item, Mapping))
    if isinstance(payload, list):
        return tuple(item for item in payload if isinstance(item, Mapping))
    return ()


def _record_percent_change(
    payload: Mapping[str, Any] | list[Any] | None,
    *keys: str,
) -> float | None:
    rows = _records(payload)
    if len(rows) < 2:
        return None
    previous = _number(rows[-2], *keys)
    current = _number(rows[-1], *keys)
    if previous is None or current is None or previous == 0:
        return None
    return (current - previous) / abs(previous) * 100.0


def _liquidation_acceleration(payload: Mapping[str, Any] | list[Any] | None) -> float | None:
    rows = _records(payload)
    if len(rows) < 2:
        return None

    def total(row: Mapping[str, Any]) -> float | None:
        direct = _number(row, "liquidation_usd", "liquidationUsd", "totalLiquidationUsd")
        if direct is not None:
            return direct
        long_value = _number(row, "long_liquidation", "longLiquidation", "longLiquidationUsd")
        short_value = _number(row, "short_liquidation", "shortLiquidation", "shortLiquidationUsd")
        return long_value + short_value if long_value is not None and short_value is not None else None

    previous = total(rows[-2])
    current = total(rows[-1])
    if previous is None or current is None or previous <= 0:
        return None
    return (current - previous) / previous * 100.0


def _latest_record(payload: Mapping[str, Any] | list[Any] | None) -> Mapping[str, Any] | None:
    if isinstance(payload, Mapping):
        data = payload.get("data", payload)
        if isinstance(data, Mapping):
            for key in ("list", "data", "items", "rows", "result"):
                nested = data.get(key)
                if isinstance(nested, list):
                    return _latest_record(nested)
            return data
        if isinstance(data, list):
            return _latest_record(data)
    if isinstance(payload, list):
        for item in reversed(payload):
            if isinstance(item, Mapping):
                return item
    return None


def _record_time(record: Mapping[str, Any], received_at: datetime) -> datetime | None:
    for key in ("timestamp", "time", "ts", "date", "createdAt", "updatedAt"):
        value = normalize_timestamp(record.get(key), received_at=received_at)
        if value is not None:
            return value
    return None


def _number(record: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _cmc_asset_record(payload: Mapping[str, Any] | list[Any] | None, symbol: str) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    data = payload.get("data")
    if isinstance(data, Mapping):
        candidate = data.get(symbol)
        if isinstance(candidate, Mapping):
            return candidate
        for value in data.values():
            if isinstance(value, Mapping) and str(value.get("symbol", "")).upper() == symbol:
                return value
    if isinstance(data, list):
        for value in data:
            if isinstance(value, Mapping) and str(value.get("symbol", "")).upper() == symbol:
                return value
    return None


def _clock_skew_ms(response: ProviderHttpResponse, reference: datetime) -> float | None:
    if not isinstance(response.payload, Mapping):
        return None
    status = response.payload.get("status")
    if not isinstance(status, Mapping):
        return None
    timestamp = normalize_timestamp(status.get("timestamp"), received_at=response.received_at)
    if timestamp is None:
        return None
    return (timestamp - reference).total_seconds() * 1000.0


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    target = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == target:
            return value
    return None


def _cryptopanic_items(
    payload: Mapping[str, Any] | list[Any] | None,
    *,
    received_at: datetime | None,
) -> tuple[dict[str, Any], ...]:
    """Normalize and group bounded news records without retaining article bodies."""

    reference = received_at or datetime.now(tz=UTC)
    raw_rows = payload.get("results") if isinstance(payload, Mapping) else payload
    if not isinstance(raw_rows, list):
        return ()
    grouped: dict[str, dict[str, Any]] = {}
    for row in raw_rows[:100]:
        if not isinstance(row, Mapping):
            continue
        title = str(row.get("title") or "").strip()
        normalized = re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()
        published_at = normalize_timestamp(row.get("published_at"), received_at=reference)
        if not normalized or published_at is None:
            continue
        source_value = row.get("source")
        source = str(_mapping(source_value).get("title") or _mapping(source_value).get("domain") or "unknown")
        votes = _mapping(row.get("votes"))
        important_votes = max(0.0, _number(votes, "important") or 0.0)
        positive_votes = max(0.0, _number(votes, "positive", "liked") or 0.0)
        importance = min(1.0, 0.35 + important_votes * 0.15 + positive_votes * 0.03)
        event_id = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
        current = grouped.get(event_id)
        if current is None:
            grouped[event_id] = {
                "event_id": event_id,
                "published_at": published_at,
                "importance": importance,
                "novelty": 1.0,
                "source": source,
                "sources": {source},
                "source_count": 1,
            }
            continue
        sources = cast(set[str], current["sources"])
        sources.add(source)
        current["source_count"] = len(sources)
        current["importance"] = max(float(current["importance"]), importance)
        current["published_at"] = max(cast(datetime, current["published_at"]), published_at)
        current["novelty"] = 1.0 / (1.0 + len(sources) - 1.0)
        current["source"] = ", ".join(sorted(sources))
    return tuple(
        {key: value for key, value in item.items() if key != "sources"}
        for item in grouped.values()
    )
