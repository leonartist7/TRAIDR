import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from data_pipeline.bitunix_futures_adapter import BitunixFuturesAdapter, PUBLIC_HEADERS
from data_pipeline.bitunix_models import BitunixCockpitSnapshot


NOW = datetime(2026, 1, 1, 12, tzinfo=UTC)


def test_bitunix_cockpit_snapshot_uses_mocked_public_transport_only() -> None:
    adapter = BitunixFuturesAdapter(_fixture_transport(NOW), now=NOW)

    result = asyncio.run(adapter.fetch_cockpit_snapshot("HYPEUSDT", "1h", "15"))

    assert result.ok
    assert isinstance(result.value, BitunixCockpitSnapshot)
    assert result.value.can_execute_trades is False
    assert result.value.symbol == "HYPEUSDT"
    assert result.value.depth_delta.depth_delta_percent == 75
    assert "BITUNIX_COCKPIT_OK" in result.reason_codes
    assert not any("KEY" in key.upper() or "SECRET" in key.upper() for key in PUBLIC_HEADERS)


def test_bitunix_adapter_rejects_unsupported_symbol_or_interval() -> None:
    adapter = BitunixFuturesAdapter(_fixture_transport(NOW), now=NOW)

    bad_symbol = asyncio.run(adapter.fetch_cockpit_snapshot("DOGEUSDT", "1h", "15"))
    bad_interval = asyncio.run(adapter.fetch_cockpit_snapshot("BTCUSDT", "2h", "15"))

    assert bad_symbol.status == "INSUFFICIENT_DATA"
    assert bad_interval.status == "INSUFFICIENT_DATA"


def test_bitunix_adapter_network_failure_returns_insufficient_data() -> None:
    async def failing_transport(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        raise httpx.ConnectError("network blocked")

    adapter = BitunixFuturesAdapter(failing_transport, now=NOW)

    result = asyncio.run(adapter.fetch_tickers(("BTCUSDT",)))

    assert result.status == "INSUFFICIENT_DATA"
    assert result.reason_codes == ("BITUNIX_HTTP_FAILED",)


def test_bitunix_adapter_malformed_or_missing_data_fails_closed() -> None:
    adapter = BitunixFuturesAdapter(lambda path, params: {"code": 0}, now=NOW)

    result = asyncio.run(adapter.fetch_kline("BTCUSDT", "1m"))

    assert result.status == "INSUFFICIENT_DATA"
    assert result.value is None


def test_bitunix_adapter_drops_individual_malformed_candles() -> None:
    def transport(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        return {
            "code": 0,
            "data": [
                {
                    "time": str(int(NOW.timestamp() * 1000) - 7_200_000),
                    "open": "65.769",
                    "high": "66.853",
                    "low": "65.771",
                    "close": "66.813",
                    "quoteVol": "75852.81",
                    "baseVol": "5035332.09824",
                },
                {
                    "time": str(int(NOW.timestamp() * 1000) - 3_600_000),
                    "open": "67",
                    "high": "68",
                    "low": "66",
                    "close": "67.5",
                    "quoteVol": "1000",
                    "baseVol": "10",
                },
                {
                    "time": str(int(NOW.timestamp() * 1000)),
                    "open": "67.5",
                    "high": "69",
                    "low": "67",
                    "close": "68.5",
                    "quoteVol": "1200",
                    "baseVol": "12",
                },
            ],
        }

    adapter = BitunixFuturesAdapter(transport, now=NOW)

    result = asyncio.run(adapter.fetch_kline("HYPEUSDT", "1h"))

    assert result.ok
    assert len(result.value) == 2
    assert "BITUNIX_KLINE_DROPPED_MALFORMED_CANDLES" in result.reason_codes


def test_bitunix_adapter_stale_candles_fail_closed() -> None:
    stale_now = NOW + timedelta(days=2)
    adapter = BitunixFuturesAdapter(_fixture_transport(NOW), now=stale_now)

    result = asyncio.run(adapter.fetch_kline("BTCUSDT", "1h"))

    assert result.status == "INSUFFICIENT_DATA"
    assert result.reason_codes == ("BITUNIX_KLINE_STALE",)


def _fixture_transport(now: datetime):
    base_time = int(now.timestamp() * 1000)

    def transport(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        symbol = params.get("symbol") or params.get("symbols", "HYPEUSDT").split(",")[0]
        if path.endswith("/tickers"):
            return {
                "code": 0,
                "data": [
                    {
                        "symbol": symbol,
                        "markPrice": "68.8",
                        "lastPrice": "68.9",
                        "open": "66.0",
                        "last": "68.9",
                        "quoteVol": "1000000",
                        "baseVol": "15000",
                        "high": "70.0",
                        "low": "65.0",
                    }
                ],
            }
        if path.endswith("/kline"):
            return {
                "code": 0,
                "data": [
                    {
                        "time": str(base_time - (2 - index) * 3_600_000),
                        "open": str(66 + index),
                        "high": str(67 + index),
                        "low": str(65 + index),
                        "close": str(66.5 + index),
                        "quoteVol": str(1000 + index),
                        "baseVol": str(10 + index),
                        "type": "LAST_PRICE",
                    }
                    for index in range(3)
                ],
            }
        if path.endswith("/funding_rate"):
            return {
                "code": 0,
                "data": {
                    "symbol": symbol,
                    "markPrice": "68.8",
                    "lastPrice": "68.9",
                    "fundingRate": "0.0001",
                    "fundingInterval": "8",
                    "nextFundingTime": str(base_time + 3_600_000),
                    "maxFundingRate": "0.003",
                    "minFundingRate": "-0.003",
                },
            }
        if path.endswith("/depth"):
            return {
                "code": 0,
                "data": {
                    "bids": [["68.8", "6"]],
                    "asks": [["68.9", "2"]],
                },
            }
        raise AssertionError(f"unexpected path {path}")

    return transport
