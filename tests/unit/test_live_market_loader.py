from datetime import datetime, timezone

from data_pipeline.defillama_adapter import DefiLlamaAdapter
from data_pipeline.live_market_loader import LiveMarketLoader
from data_pipeline.source_registry import SourceRegistry

NOW = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)


def fixture_payload() -> dict[str, object]:
    return {
        "slug": "solana",
        "symbol": "SOL",
        "chain": "Solana",
        "priceUsd": "4.20",
        "tvl": "12000",
        "volume24hUsd": "3000",
        "timestamp": 1779623940,
    }


def test_live_market_loader_is_optional_and_fails_closed_without_source() -> None:
    result = LiveMarketLoader().fetch("coingecko", "solana")

    assert result.ok is False
    assert result.reason_codes == ("SOURCE_UNAVAILABLE",)


def test_live_market_loader_uses_only_registered_mocked_transports() -> None:
    loader = LiveMarketLoader.from_optional_transports(
        defillama_transport=lambda _pair: fixture_payload(),
        now=NOW,
    )

    result = loader.fetch("defillama", "solana")

    assert result.ok is True
    assert result.value is not None
    assert result.value.provenance.source_name == "defillama"


def test_live_market_loader_first_available_does_not_invent_bullish_data() -> None:
    registry = SourceRegistry()
    registry.register(DefiLlamaAdapter(lambda _pair: None, now=NOW))
    loader = LiveMarketLoader(registry)

    result = loader.first_available("solana", ("defillama", "coingecko"))

    assert result.ok is False
    assert result.value is None
    assert result.reason_codes == (
        "LIVE_MARKET_SOURCES_INSUFFICIENT",
        "DEFILLAMA_SOURCE_MISSING",
        "SOURCE_UNAVAILABLE",
    )
