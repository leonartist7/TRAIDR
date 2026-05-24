from datetime import datetime, timezone

from data_pipeline.coingecko_adapter import CoinGeckoAdapter

NOW = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)


def coingecko_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "solana",
        "symbol": "sol",
        "asset_platform_id": "solana",
        "market_data": {
            "current_price": {"usd": "4.20"},
            "total_value_locked": {"usd": "12000"},
            "total_volume": {"usd": "3000"},
        },
        "last_updated": "2026-05-24T11:59:00+00:00",
    }
    payload.update(overrides)
    return payload


def test_coingecko_adapter_normalizes_mocked_payload() -> None:
    result = CoinGeckoAdapter(lambda _pair: coingecko_payload(), now=NOW).fetch_snapshot("solana")

    assert result.ok is True
    assert result.value is not None
    assert result.value.identity.pair_id == "solana-usd"
    assert result.value.identity.base_symbol == "SOL"
    assert result.value.provenance.source_name == "coingecko"
    assert result.value.metrics.liquidity_usd == 12000


def test_coingecko_adapter_fails_closed_without_transport_or_on_failure() -> None:
    unavailable = CoinGeckoAdapter(now=NOW).fetch_snapshot("solana")
    failed = CoinGeckoAdapter(lambda _pair: (_ for _ in ()).throw(RuntimeError("down")), now=NOW).fetch_snapshot("solana")

    assert unavailable.reason_codes == ("COINGECKO_TRANSPORT_UNAVAILABLE",)
    assert failed.reason_codes == ("COINGECKO_TRANSPORT_FAILED",)


def test_coingecko_adapter_missing_and_stale_data_are_insufficient() -> None:
    missing = CoinGeckoAdapter(lambda _pair: coingecko_payload(market_data={}), now=NOW).fetch_snapshot("solana")
    stale = CoinGeckoAdapter(
        lambda _pair: coingecko_payload(last_updated="2026-05-24T11:00:00+00:00"),
        now=NOW,
    ).fetch_snapshot("solana")

    assert missing.ok is False
    assert missing.value is None
    assert missing.reason_codes == ("MARKET_SOURCE_FIELDS_MISSING",)
    assert stale.reason_codes == ("TIMESTAMP_STALE",)
