from datetime import UTC, datetime

from data_pipeline.asset_identity import AssetIdentityRegistry
from intelligence.evidence_engine import map_news_evidence, onchain_hard_vetoes
from onchain.contracts import OnchainSafetyObservation


NOW = datetime(2026, 7, 21, 12, tzinfo=UTC)


def test_exact_bindings_resolve_and_symbol_guess_does_not() -> None:
    registry = AssetIdentityRegistry.reviewed_defaults()

    bitcoin = registry.resolve(
        source="bitunix", binding_kind="futures_symbol", source_identifier="BTCUSDT"
    )
    guessed = registry.resolve(
        source="coingecko", binding_kind="spot_id", source_identifier="BTC"
    )

    assert bitcoin is not None and bitcoin.canonical_asset_id == "asset:bitcoin"
    assert guessed is None


def test_news_is_exact_mapped_deduplicated_and_context_only() -> None:
    rows = [
        {"headline": "Bitcoin liquidity improves", "url": "https://example.test/one", "observed_at": NOW},
        {"headline": "Bitcoin liquidity improves", "url": "https://example.test/two", "observed_at": NOW},
        {"headline": "Unrelated market story", "url": "https://example.test/three", "observed_at": NOW},
    ]
    evidence = map_news_evidence(
        rows, source="coindesk", registry=AssetIdentityRegistry.reviewed_defaults(), now=NOW
    )

    assert len(evidence) == 2
    assert evidence[0]["canonical_asset_id"] == "asset:bitcoin"
    assert "NEWS_CONTEXT_ONLY" in evidence[0]["reason_codes"]
    assert evidence[1]["mapping_state"] == "MISSING"
    assert evidence[1]["relevance"] == 0.0


def test_verified_onchain_hazards_are_hard_vetoes() -> None:
    vetoes = onchain_hard_vetoes(
        OnchainSafetyObservation(
            liquidity_accessible=False,
            mint_freeze_or_sell_restriction=True,
            honeypot_tax_route_or_sellability_issue=True,
            identity_ambiguous=True,
        )
    )

    assert "ONCHAIN_HONEYPOT_OR_SELL_RESTRICTION" in vetoes
    assert "ONCHAIN_LIQUIDITY_INACCESSIBLE" in vetoes
    assert "ONCHAIN_FREEZE_OR_SELL_RESTRICTION" in vetoes
    assert "CONTRADICTORY_ASSET_IDENTITY" in vetoes
