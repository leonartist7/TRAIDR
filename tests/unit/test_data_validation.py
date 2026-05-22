from datetime import datetime, timezone

from data_pipeline.contracts import AdapterStatus
from data_pipeline.dexscreener_adapter import DexScreenerAdapter
from data_pipeline.normalization import normalize_market_record

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def fixture_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "pair_id": "sol-usdc",
        "chain_id": "solana",
        "base_symbol": "SOL",
        "quote_symbol": "USDC",
        "price_usd": "4.2",
        "liquidity_usd": "12000",
        "volume_24h_usd": "3000",
        "observed_at": "2026-05-22T11:59:00+00:00",
        "source_record_id": "fixture-1",
    }
    record.update(overrides)
    return record


def test_market_record_normalizes_fixture_snapshot() -> None:
    result = normalize_market_record(fixture_record(), source_name="fixture", now=NOW)

    assert result.ok is True
    assert result.value is not None
    assert result.value.identity.pair_id == "sol-usdc"
    assert result.value.metrics.liquidity_usd == 12000
    assert result.value.provenance.source_name == "fixture"


def test_missing_stale_and_contradictory_market_data_are_insufficient() -> None:
    missing = normalize_market_record(None, source_name="fixture", now=NOW)
    stale = normalize_market_record(
        fixture_record(observed_at="2026-05-22T11:00:00+00:00"),
        source_name="fixture",
        now=NOW,
    )
    contradictory = normalize_market_record(
        fixture_record(base_symbol="USDC", quote_symbol="USDC"),
        source_name="fixture",
        now=NOW,
    )

    assert missing.status is AdapterStatus.INSUFFICIENT_DATA
    assert missing.reason_codes == ("MARKET_SOURCE_MISSING",)
    assert stale.reason_codes == ("TIMESTAMP_STALE",)
    assert contradictory.reason_codes == ("MARKET_IDENTITY_CONTRADICTORY",)


def test_dexscreener_requires_injected_transport() -> None:
    absent = DexScreenerAdapter(now=NOW).fetch_snapshot("sol-usdc")
    mocked = DexScreenerAdapter(lambda _pair: fixture_record(), now=NOW).fetch_snapshot(
        "sol-usdc"
    )

    assert absent.reason_codes == ("DEXSCREENER_TRANSPORT_UNAVAILABLE",)
    assert mocked.ok is True

