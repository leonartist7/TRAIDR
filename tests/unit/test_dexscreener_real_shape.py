from datetime import datetime, timezone

from data_pipeline.contracts import AdapterStatus
from data_pipeline.dexscreener_adapter import (
    DexScreenerAdapter,
    DexScreenerHTTPError,
    default_dexscreener_transport,
)


NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_dexscreener_real_pair_shape_normalizes() -> None:
    adapter = DexScreenerAdapter(lambda _pair_ref: _dex_response(), now=NOW)

    result = adapter.fetch_snapshot("solana/PAIR123")

    assert result.ok
    assert result.value is not None
    assert result.value.identity.pair_id == "PAIR123"
    assert result.value.identity.chain_id == "solana"
    assert result.value.identity.base_symbol == "BONK"
    assert result.value.metrics.price_usd > 0


def test_dexscreener_missing_market_fields_is_insufficient() -> None:
    payload = _dex_response()
    del payload["pairs"][0]["liquidity"]
    adapter = DexScreenerAdapter(lambda _pair_ref: payload, now=NOW)

    result = adapter.fetch_snapshot("solana/PAIR123")

    assert result.status is AdapterStatus.INSUFFICIENT_DATA
    assert "MARKET_SOURCE_FIELDS_MISSING" in result.reason_codes


def test_dexscreener_http_error_is_insufficient() -> None:
    adapter = DexScreenerAdapter(
        lambda _pair_ref: (_ for _ in ()).throw(DexScreenerHTTPError("boom")),
        now=NOW,
    )

    result = adapter.fetch_snapshot("solana/PAIR123")

    assert result.status is AdapterStatus.INSUFFICIENT_DATA
    assert "DEXSCREENER_HTTP_ERROR" in result.reason_codes


def test_default_transport_uses_dexscreener_pair_endpoint(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_exc_info):
            return None

        def read(self):
            return b'{"pairs":[]}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("data_pipeline.dexscreener_adapter.urlopen", fake_urlopen)

    payload = default_dexscreener_transport("solana/PAIR123")

    assert payload == {"pairs": []}
    assert captured["url"].endswith("/solana/PAIR123")
    assert captured["timeout"] == 10


def _dex_response():
    return {
        "schemaVersion": "1.0.0",
        "pairs": [
            {
                "chainId": "solana",
                "dexId": "raydium",
                "pairAddress": "PAIR123",
                "url": "https://dexscreener.com/solana/PAIR123",
                "baseToken": {"address": "BASE123", "name": "Bonk", "symbol": "BONK"},
                "quoteToken": {"address": "QUOTE123", "name": "USD Coin", "symbol": "USDC"},
                "priceUsd": "0.000021",
                "liquidity": {"usd": 2500},
                "volume": {"h24": 700},
            }
        ],
    }
