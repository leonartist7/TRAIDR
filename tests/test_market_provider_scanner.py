from __future__ import annotations

import asyncio

import duckdb
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from data_pipeline.market_data_providers import (
    BitunixPrivateReadOnlyBoundary,
    CoinGlassProvider,
    CoinGeckoProvider,
    CoinMarketCapProvider,
)
from data_pipeline.provider_contracts import (
    ProviderCapability,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderHttpResponse,
    ProviderObservation,
    ProviderResult,
    merge_provider_observations,
    normalize_timestamp,
)
from scoring.live_scanner import ScannerInput, score_scanner_input
from storage.market_repository import MarketRepository
from scheduler.live_service import LiveResearchService
from storage.schema import initialize_schema
from intelligence.production_models import SignalDirection


NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)


def _health(provider: str) -> ProviderHealth:
    return ProviderHealth(
        provider=provider,
        checked_at=NOW,
        status=ProviderHealthStatus.HEALTHY,
        latency_ms=5.0,
        clock_skew_ms=0.0,
        consecutive_failures=0,
        rate_limited=False,
        reason_codes=("TEST_HEALTHY",),
    )


def _observation(
    provider: str,
    price: float,
    *,
    observed_at: datetime = NOW,
) -> ProviderResult[ProviderObservation]:
    value = ProviderObservation(
        provider=provider,
        instrument_id="bitunix:BTCUSDT",
        observed_at=observed_at,
        received_at=NOW,
        fields={"price_usd": price, "funding_rate": 0.0002},
        capabilities=(ProviderCapability.MARKET_DATA,),
    )
    return ProviderResult(
        provider=provider,
        status=ProviderHealthStatus.HEALTHY,
        value=value,
        health=_health(provider),
        reason_codes=("TEST_OBSERVATION",),
    )


def test_future_timestamps_fail_closed() -> None:
    assert normalize_timestamp(NOW + timedelta(minutes=3), received_at=NOW) is None
    assert normalize_timestamp(NOW + timedelta(seconds=30), received_at=NOW) == NOW + timedelta(seconds=30)


def test_source_merge_prefers_bitunix_and_surfaces_critical_conflict() -> None:
    bundle = merge_provider_observations(
        "bitunix:BTCUSDT",
        (_observation("coingecko", 100.0), _observation("bitunix_public", 104.0)),
        now=NOW,
    )

    assert bundle.fields["price_usd"] == 104.0
    assert bundle.field_sources["price_usd"] == "bitunix_public"
    assert bundle.has_critical_conflict
    assert "CRITICAL_SOURCE_CONFLICT" in bundle.reason_codes


def test_source_merge_rejects_stale_observations_before_selection() -> None:
    at_boundary = merge_provider_observations(
        "bitunix:BTCUSDT",
        (_observation("bitunix_public", 100.0, observed_at=NOW - timedelta(minutes=5)),),
        now=NOW,
    )
    stale = merge_provider_observations(
        "bitunix:BTCUSDT",
        (_observation("bitunix_public", 100.0, observed_at=NOW - timedelta(minutes=5, seconds=1)),),
        now=NOW,
    )

    assert at_boundary.status is ProviderHealthStatus.HEALTHY
    assert at_boundary.fields["price_usd"] == 100.0
    assert stale.status is ProviderHealthStatus.INSUFFICIENT_DATA
    assert stale.fields == {}
    assert "STALE_PROVIDER_OBSERVATION" in stale.reason_codes
    assert "NO_FRESH_PROVIDER_OBSERVATION" in stale.reason_codes


def test_provider_honors_case_insensitive_retry_after_header() -> None:
    calls = 0
    delays: list[float] = []

    async def transport(
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> ProviderHttpResponse:
        del url, params, headers
        nonlocal calls
        calls += 1
        if calls == 1:
            return ProviderHttpResponse(429, {}, headers={"retry-after": "4"}, received_at=NOW)
        return ProviderHttpResponse(200, {}, received_at=NOW)

    async def sleep(delay: float) -> None:
        delays.append(delay)

    provider = CoinMarketCapProvider(transport=transport)
    provider.sleep = sleep
    response, reasons = asyncio.run(
        provider._request("/test", params={})
    )

    assert response is not None
    assert response.status_code == 200
    assert calls == 2
    assert delays == [4.0]
    assert "PROVIDER_RATE_LIMITED" in reasons


def test_bitunix_private_boundary_has_no_account_action_path() -> None:
    boundary = BitunixPrivateReadOnlyBoundary()
    results = [
        asyncio.run(boundary.fetch_account_balance()),
        asyncio.run(boundary.fetch_positions()),
        asyncio.run(boundary.fetch_leverage()),
        asyncio.run(boundary.fetch_protection_orders()),
    ]

    assert all(result.status is ProviderHealthStatus.INSUFFICIENT_DATA for result in results)
    assert all(result.can_execute_trades is False for result in results)
    assert all("NO_TRADING_OR_WITHDRAWAL_CAPABILITY" in result.reason_codes for result in results)


def test_coinglass_requires_explicit_api_key() -> None:
    result = asyncio.run(CoinGlassProvider().fetch("BTCUSDT"))

    assert result.status is ProviderHealthStatus.INSUFFICIENT_DATA
    assert "COINGLASS_API_KEY_MISSING" in result.reason_codes
    assert result.can_execute_trades is False


def test_coinglass_normalizes_derivatives_metrics() -> None:
    async def transport(
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> ProviderHttpResponse:
        del params, headers
        if "funding-rate" in url:
            payload: Any = {"data": [{"fundingRate": "0.0004", "timestamp": NOW.isoformat()}]}
        elif "open-interest" in url:
            payload = {"data": [{"openInterest": "1000000", "changePercent": "4", "timestamp": NOW.isoformat()}]}
        elif "liquidation" in url:
            payload = {"data": [{"longLiquidationUsd": "700", "shortLiquidationUsd": "300", "timestamp": NOW.isoformat()}]}
        else:
            payload = {"data": [{"longShortRatio": "1.2", "timestamp": NOW.isoformat()}]}
        return ProviderHttpResponse(200, payload, received_at=NOW)

    result = asyncio.run(CoinGlassProvider(api_key="test-only", transport=transport).fetch("BTCUSDT"))

    assert result.ok
    assert result.value is not None
    assert result.value.fields["funding_rate"] == 0.0004
    assert result.value.fields["oi_change_pct"] == 4.0
    assert result.value.fields["liquidation_pressure"] == 0.4
    assert result.value.can_execute_trades is False


def test_coingecko_current_and_history_are_read_only() -> None:
    async def transport(
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> ProviderHttpResponse:
        del headers
        if url.endswith("market_chart"):
            payload: Any = {"prices": [[1_700_000_000_000, 100.0], [1_700_086_400_000, 110.0]]}
        else:
            payload = {
                "id": "bitcoin",
                "name": "Bitcoin",
                "symbol": "btc",
                "last_updated": NOW.isoformat(),
                "market_data": {
                    "current_price": {"usd": 100.0},
                    "total_volume": {"usd": 1_000_000.0},
                    "market_cap": {"usd": 2_000_000_000.0},
                    "price_change_percentage_24h": 2.0,
                },
            }
        return ProviderHttpResponse(200, payload, received_at=NOW)

    provider = CoinGeckoProvider(coin_ids={"BTC": "bitcoin"}, transport=transport)
    current = asyncio.run(provider.fetch("BTCUSDT"))
    history = asyncio.run(provider.fetch_history("BTCUSDT", days=2))

    assert current.ok and current.value is not None
    assert current.value.fields["price_usd"] == 100.0
    assert history.ok and history.value is not None
    assert len(history.value) == 2
    assert current.value.can_execute_trades is False


def test_coinmarketcap_transport_failure_returns_insufficient_data() -> None:
    async def transport(
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> ProviderHttpResponse:
        del url, params, headers
        raise OSError("offline")

    result = asyncio.run(CoinMarketCapProvider(transport=transport).fetch_rankings(limit=5))

    assert result.status is ProviderHealthStatus.INSUFFICIENT_DATA
    assert "PROVIDER_TRANSPORT_FAILED" in result.reason_codes
    assert result.can_execute_trades is False


def test_coinmarketcap_unsupported_indicator_and_event_routes_fail_closed() -> None:
    provider = CoinMarketCapProvider()
    indicators = asyncio.run(provider.fetch_technical_indicators("BTC"))
    events = asyncio.run(provider.fetch_events())

    assert indicators.status is ProviderHealthStatus.INSUFFICIENT_DATA
    assert "CMC_TECHNICAL_INDICATORS_API_UNAVAILABLE" in indicators.reason_codes
    assert events.status is ProviderHealthStatus.INSUFFICIENT_DATA
    assert "CMC_EVENTS_API_UNAVAILABLE" in events.reason_codes
    assert indicators.can_execute_trades is False
    assert events.can_execute_trades is False


def test_scanner_exposes_all_factor_contributions_and_stays_non_executing() -> None:
    fields = {
        "price_structure": 0.5,
        "volume_24h_usd": 1000.0,
        "order_book_imbalance": 0.5,
        "trade_delta": 0.4,
        "funding_rate": -0.0005,
        "oi_change_pct": 5.0,
        "liquidation_pressure": -0.4,
        "btc_eth_correlation": 0.5,
        "news_catalyst": 0.5,
        "risk_reward": 3.0,
    }
    score = score_scanner_input(
        ScannerInput(
            instrument_id="bitunix:BTCUSDT",
            fields=fields,
            volume_reference=1000.0,
        )
    )

    assert score.direction is SignalDirection.LONG
    assert score.score is not None and score.score >= 62.0
    assert len(score.factor_breakdown()) == 10
    assert all(row["can_execute_trades"] is False for row in score.factor_breakdown())


def test_scanner_defaults_to_insufficient_data_when_factors_are_missing() -> None:
    score = score_scanner_input(
        ScannerInput(
            instrument_id="bitunix:BTCUSDT",
            fields={"price_structure": 0.5},
        )
    )

    assert score.direction is SignalDirection.NO_TRADE
    assert score.status == "INSUFFICIENT_DATA"
    assert "SCANNER_REQUIRED_FACTORS_MISSING" in score.reason_codes
    assert len(score.factor_breakdown()) == 10
    assert any("SCANNER_MISSING_VOLUME" in row["reason_codes"] for row in score.factor_breakdown())
    price_row = next(row for row in score.factor_breakdown() if row["factor"] == "price_structure")
    assert price_row["raw_value"] == 0.5
    assert price_row["long_contribution"] == 0.0


def test_scanner_rejects_stale_observation_when_reference_is_supplied() -> None:
    fields = {
        "price_structure": 0.5,
        "volume_24h_usd": 1000.0,
        "order_book_imbalance": 0.5,
        "trade_delta": 0.4,
        "funding_rate": -0.0005,
        "oi_change_pct": 5.0,
        "liquidation_pressure": -0.4,
        "btc_eth_correlation": 0.5,
        "news_catalyst": 0.5,
        "risk_reward": 3.0,
    }
    score = score_scanner_input(
        ScannerInput(
            instrument_id="bitunix:BTCUSDT",
            fields=fields,
            observed_at=NOW - timedelta(hours=6),
            reference_at=NOW,
            volume_reference=1000.0,
        )
    )

    assert score.direction is SignalDirection.NO_TRADE
    assert score.status == "INSUFFICIENT_DATA"
    assert "SCANNER_STALE_OBSERVATION" in score.reason_codes
    price_row = next(row for row in score.factor_breakdown() if row["factor"] == "price_structure")
    assert price_row["raw_value"] == 0.5
    assert price_row["long_contribution"] == 0.0


def test_service_scanner_wiring_stays_fail_closed_without_correlation_or_catalyst() -> None:
    service = object.__new__(LiveResearchService)
    service._latest_trade_delta = {"bitunix:BTCUSDT": 0.25}
    service._news_cache = {}
    feature = SimpleNamespace(
        instrument_id="bitunix:BTCUSDT",
        observed_at=NOW,
        features={
            "trend_strength_pct": 0.5,
            "last_price": 100.0,
            "support": 95.0,
            "resistance": 110.0,
        },
    )
    score = service._build_scanner_score(
        symbol="BTCUSDT",
        feature=feature,
        candles=[],
        depth_imbalance=0.2,
        funding=None,
        external_context={
            "coinglass_funding_rate": -0.0001,
            "coinglass_oi_change_pct": 4.0,
            "coinglass_liquidation_pressure": -0.2,
        },
        canonical_asset_id=None,
        reference_at=NOW,
    )

    assert score.direction is SignalDirection.NO_TRADE
    assert score.status == "INSUFFICIENT_DATA"
    reasons = {reason for row in score.factor_breakdown() for reason in row["reason_codes"]}
    assert "SCANNER_MISSING_BTC_ETH_CORRELATION" in reasons
    assert "SCANNER_MISSING_NEWS_CATALYST" in reasons


def test_scanner_breakdown_persists_as_read_only_research_state() -> None:
    fields = {
        "price_structure": 0.5,
        "volume_24h_usd": 1000.0,
        "order_book_imbalance": 0.5,
        "trade_delta": 0.4,
        "funding_rate": -0.0005,
        "oi_change_pct": 5.0,
        "liquidation_pressure": -0.4,
        "btc_eth_correlation": 0.5,
        "news_catalyst": 0.5,
        "risk_reward": 3.0,
    }
    score = score_scanner_input(ScannerInput(instrument_id="bitunix:BTCUSDT", fields=fields, observed_at=NOW))
    connection = duckdb.connect(":memory:")
    try:
        initialize_schema(connection)
        repository = MarketRepository(connection)
        assert repository.record_scanner_score(score)
        row = connection.execute(
            "SELECT direction, can_execute_trades, factor_breakdown_json FROM market_scanner_scores"
        ).fetchone()
        assert row is not None
        assert row[0] == "LONG"
        assert row[1] is False
        assert "price_structure" in row[2]
    finally:
        connection.close()
