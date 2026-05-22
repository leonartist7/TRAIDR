from datetime import datetime, timezone

from data_pipeline.dexscreener_adapter import DexScreenerAdapter
from data_pipeline.source_registry import SourceRegistry

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_source_registry_fails_closed_until_source_registered() -> None:
    registry = SourceRegistry()
    unavailable = registry.fetch("dexscreener", "pair")
    registry.register(
        DexScreenerAdapter(
            lambda _pair: {
                "pair_id": "pair",
                "chain_id": "solana",
                "base_symbol": "SOL",
                "quote_symbol": "USDC",
                "price_usd": "4.2",
                "liquidity_usd": "10000",
                "volume_24h_usd": "2000",
                "observed_at": "2026-05-22T11:59:00+00:00",
                "source_record_id": "fixture-registry",
            },
            now=NOW,
        )
    )
    available = registry.fetch("dexscreener", "pair")

    assert unavailable.reason_codes == ("SOURCE_UNAVAILABLE",)
    assert available.ok is True

