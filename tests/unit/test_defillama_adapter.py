from datetime import datetime, timezone

from data_pipeline.defillama_adapter import DefiLlamaAdapter

NOW = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)


def defillama_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "slug": "solana",
        "symbol": "SOL",
        "chain": "Solana",
        "priceUsd": "4.20",
        "tvl": "12000",
        "volume24hUsd": "3000",
        "timestamp": 1779623940,
    }
    payload.update(overrides)
    return payload


def test_defillama_adapter_normalizes_mocked_payload() -> None:
    result = DefiLlamaAdapter(lambda _pair: defillama_payload(), now=NOW).fetch_snapshot("solana")

    assert result.ok is True
    assert result.value is not None
    assert result.value.identity.pair_id == "solana-usd"
    assert result.value.identity.chain_id == "Solana"
    assert result.value.provenance.source_name == "defillama"
    assert result.value.metrics.volume_24h_usd == 3000


def test_defillama_adapter_fails_closed_without_transport_or_on_failure() -> None:
    unavailable = DefiLlamaAdapter(now=NOW).fetch_snapshot("solana")
    failed = DefiLlamaAdapter(lambda _pair: (_ for _ in ()).throw(RuntimeError("down")), now=NOW).fetch_snapshot("solana")

    assert unavailable.reason_codes == ("DEFILLAMA_TRANSPORT_UNAVAILABLE",)
    assert failed.reason_codes == ("DEFILLAMA_TRANSPORT_FAILED",)


def test_defillama_adapter_missing_and_stale_data_are_insufficient() -> None:
    missing = DefiLlamaAdapter(lambda _pair: defillama_payload(priceUsd=None), now=NOW).fetch_snapshot("solana")
    stale = DefiLlamaAdapter(
        lambda _pair: defillama_payload(timestamp=1779620400),
        now=NOW,
    ).fetch_snapshot("solana")

    assert missing.reason_codes == ("MARKET_SOURCE_FIELDS_MISSING",)
    assert stale.reason_codes == ("TIMESTAMP_STALE",)
