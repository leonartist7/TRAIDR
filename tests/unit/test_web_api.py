from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from data_pipeline.bitunix_models import BitunixCandle, BitunixTradingPair
from data_pipeline.provider_contracts import ProviderCapability, ProviderObservation
from intelligence.production_models import DataHealth, MarketChannel, SignalDirection
from storage.duckdb_store import DuckDBStore
from storage.market_repository import MarketRepository
from storage.schema import initialize_schema
from scoring.live_scanner import ScannerFactor, ScannerScore
from scoring.shadow_strategy import classify_shadow_strategy
from web_api import create_app
from web_api.app import validate_loopback_host

OPENAPI_PATHS = Path(__file__).parents[1] / "fixtures" / "web_api_openapi_paths.json"


def _seed_database(database: Path) -> None:
    now = datetime.now(tz=UTC).replace(microsecond=0)
    score = ScannerScore(
        instrument_id="bitunix:BTCUSDT",
        status="OK",
        direction=SignalDirection.LONG,
        score=74.0,
        long_score=74.0,
        short_score=26.0,
        risk_score=18.0,
        factors=(
            ScannerFactor(
                name="price_structure",
                weight=20.0,
                raw_value=0.8,
                normalized_value=0.8,
                long_contribution=8.0,
                short_contribution=-8.0,
                explanation="Trend structure supports the long side.",
                source="fixture",
            ),
        ),
        conflicts=(),
        reason_codes=("TEST_SCORE",),
        observed_at=now,
    )
    candle = BitunixCandle(
        symbol="BTCUSDT",
        interval="1h",
        time_ms=int(now.timestamp() * 1000) - 3_600_000,
        open=100,
        high=105,
        low=99,
        close=104,
        quote_volume=1_000,
        base_volume=10,
    )
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        repository = MarketRepository(store.connection)
        assert repository.upsert_instrument(
            BitunixTradingPair(
                symbol="BTCUSDT",
                base="BTC",
                quote="USDT",
                min_trade_volume=1,
                min_buy_price_offset=0,
                max_sell_price_offset=0,
                max_limit_order_volume=100,
                max_market_order_volume=100,
                base_precision=3,
                quote_precision=2,
                min_leverage=1,
                max_leverage=10,
                default_leverage=1,
                default_margin_mode="isolated",
                price_protect_scope=1,
                symbol_status="TRADING",
                is_api_supported=True,
                max_funding_rate=1,
                min_funding_rate=-1,
            ),
            now=now,
        ) == "bitunix:BTCUSDT"
        assert repository.record_scanner_score(score)
        shadow_fields = {
            "price_change_1h_pct": 1.0,
            "oi_change_pct_1h": 2.0,
            "funding_rate": 0.0001,
            "liquidation_pressure": 0.1,
            "taker_buy_sell_imbalance": 0.2,
        }
        shadow = ProviderObservation(
            provider="traidr_shadow_strategy",
            instrument_id="bitunix:BTCUSDT",
            observed_at=now,
            received_at=now,
            fields=shadow_fields,
            capabilities=(ProviderCapability.MARKET_REGIME,),
            reason_codes=("SHADOW_ONLY", "ZERO_SCORING_WEIGHT"),
        )
        assert repository.record_shadow_evidence(
            shadow,
            classify_shadow_strategy(
                "bitunix:BTCUSDT",
                shadow_fields,
                observed_at=now,
                reference_at=now,
            ),
        )
        assert repository.upsert_candles(
            "bitunix:BTCUSDT",
            "1h",
            [candle],
            received_at=now,
        ) == 1


def test_api_missing_database_is_fail_closed_and_does_not_write(tmp_path: Path) -> None:
    database = tmp_path / "missing-api.duckdb"
    client = TestClient(create_app(database))

    response = client.get("/api/v1/status", headers={"X-Request-ID": "test-request-1"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "INSUFFICIENT_DATA"
    assert payload["data"]["database_exists"] is False
    assert all(item["can_execute_trades"] is False for item in payload["data"]["provider_health"])
    assert "api_key" not in response.text.lower()
    assert payload["can_execute_trades"] is False
    assert payload["request_id"] == "test-request-1"
    assert response.headers["X-Request-ID"] == "test-request-1"
    assert database.exists() is False


def test_api_scanner_overview_and_chart_are_read_only_views(tmp_path: Path) -> None:
    database = tmp_path / "api.duckdb"
    _seed_database(database)
    client = TestClient(create_app(database))

    scanner = client.get("/api/v1/scanner?limit=10").json()
    scanner_detail = client.get("/api/v1/scanner/bitunix:BTCUSDT").json()
    overview = client.get("/api/v1/overview?limit=10").json()
    markets = client.get("/api/v1/markets?limit=10").json()
    chart = client.get("/api/v1/markets/bitunix:BTCUSDT/chart?interval=1h&limit=10").json()

    assert scanner["status"] == "OK"
    assert scanner["data"]["rows"][0]["direction"] == "LONG"
    assert scanner["data"]["rows"][0]["factors"][0]["raw_value"] == 0.8
    assert scanner["data"]["rows"][0]["shadow"]["setup_class"] == "MOMENTUM_BUILD"
    assert scanner["data"]["rows"][0]["shadow"]["scoring_weight"] == 0.0
    assert scanner_detail["data"]["rows"][0]["factors"][0]["factor"] == "price_structure"
    assert overview["data"]["scanner"][0]["instrument_id"] == "bitunix:BTCUSDT"
    assert overview["data"]["shadow_evidence"][0]["probability_state"] == "UNCALIBRATED"
    assert markets["status"] == "OK"
    assert markets["data"]["instruments"][0]["instrument_id"] == "bitunix:BTCUSDT"
    assert chart["status"] == "OK"
    assert chart["data"]["candles"][0]["close"] == 104.0
    assert scanner["can_execute_trades"] is False
    assert chart["data"]["candles"][0]["can_execute_trades"] is False


def test_api_contract_is_loopback_only_and_get_only(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "contract.duckdb"))

    openapi = client.get("/openapi.json").json()
    expected_paths = json.loads(OPENAPI_PATHS.read_text(encoding="utf-8"))

    assert {path: sorted(spec) for path, spec in openapi["paths"].items()} == expected_paths
    with pytest.raises(ValueError, match="127.0.0.1"):
        validate_loopback_host("0.0.0.0")
    with pytest.raises(ValueError, match="127.0.0.1"):
        validate_loopback_host("localhost")


def test_api_empty_stale_and_degraded_states_are_truthful(tmp_path: Path) -> None:
    empty_database = tmp_path / "empty.duckdb"
    with DuckDBStore(empty_database) as store:
        initialize_schema(store.connection)
    empty_payload = TestClient(create_app(empty_database)).get("/api/v1/status").json()

    stale_database = tmp_path / "stale.duckdb"
    stale_at = datetime.now(tz=UTC) - timedelta(minutes=2)
    with DuckDBStore(stale_database) as store:
        initialize_schema(store.connection)
        MarketRepository(store.connection).upsert_health(
            DataHealth(
                source="bitunix",
                instrument_id="bitunix:BTCUSDT",
                channel=MarketChannel.TICKER,
                status="HEALTHY",
                checked_at=stale_at,
                last_event_at=stale_at,
                coverage=1.0,
                reason_codes=(),
            )
        )
    stale_payload = TestClient(create_app(stale_database)).get("/api/v1/status").json()

    degraded_database = tmp_path / "degraded.duckdb"
    with DuckDBStore(degraded_database) as store:
        initialize_schema(store.connection)
        MarketRepository(store.connection).upsert_health(
            DataHealth(
                source="bitunix",
                instrument_id="bitunix:BTCUSDT",
                channel=MarketChannel.TICKER,
                status="DEGRADED",
                checked_at=datetime.now(tz=UTC),
                coverage=0.4,
                reason_codes=("TEST_DEGRADED",),
            )
        )
    degraded_payload = TestClient(create_app(degraded_database)).get("/api/v1/status").json()

    assert empty_payload["status"] == "INSUFFICIENT_DATA"
    assert empty_payload["data"]["database_exists"] is True
    assert stale_payload["status"] == "DEGRADED"
    assert "LOCAL_SERVICE_DEGRADED" in stale_payload["reason_codes"]
    assert degraded_payload["status"] == "DEGRADED"


def test_api_conflict_and_malformed_database_fail_closed(tmp_path: Path) -> None:
    conflict_database = tmp_path / "conflict.duckdb"
    _seed_database(conflict_database)
    now = datetime.now(tz=UTC).replace(microsecond=0) + timedelta(seconds=1)
    with DuckDBStore(conflict_database) as store:
        assert MarketRepository(store.connection).record_scanner_score(
            ScannerScore(
                instrument_id="bitunix:BTCUSDT",
                status="NO_TRADE",
                direction=SignalDirection.NO_TRADE,
                score=None,
                long_score=None,
                short_score=None,
                risk_score=None,
                factors=(),
                conflicts=("SOURCE_CONFLICT",),
                reason_codes=("SCANNER_CRITICAL_SOURCE_CONFLICT",),
                observed_at=now,
            )
        )
    conflict_payload = TestClient(create_app(conflict_database)).get("/api/v1/scanner").json()

    malformed_database = tmp_path / "malformed.duckdb"
    malformed_database.write_bytes(b"not a duckdb database")
    malformed_response = TestClient(create_app(malformed_database)).get("/api/v1/status")

    assert conflict_payload["data"]["rows"][0]["status"] == "NO_TRADE"
    assert conflict_payload["data"]["rows"][0]["conflicts"] == ["SOURCE_CONFLICT"]
    assert malformed_response.status_code == 500
    assert malformed_response.json()["status"] == "ERROR"
    assert malformed_response.json()["data"]["code"] == "READ_MODEL_ERROR"
    assert "duckdb" not in malformed_response.text.lower()


def test_api_validation_and_cors_are_safe(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "validation.duckdb"))

    invalid = client.get("/api/v1/scanner?limit=0").json()
    allowed = client.get(
        "/health",
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    remote = client.get(
        "/health",
        headers={"Origin": "https://remote.example"},
    )

    assert invalid["status"] == "ERROR"
    assert invalid["data"]["code"] == "REQUEST_VALIDATION"
    assert invalid["can_execute_trades"] is False
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert "access-control-allow-origin" not in remote.headers
