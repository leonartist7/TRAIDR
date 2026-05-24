from datetime import datetime, timezone

from data_pipeline.live_market_loader import LiveMarketLoader
from token_detail.detail_builder import build_token_detail

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_fixture_token_detail_works_offline() -> None:
    report = build_token_detail(fixture=True)

    assert report.status == "OK"
    assert report.identity is not None
    assert report.identity.pair_id == "fixture-sol-usdc"
    assert report.can_execute_trades is False
    assert report.technical_vector is not None
    assert report.anti_rug.status == "CLEAR"
    assert report.why_interesting
    assert report.why_risky


def test_real_source_token_detail_uses_mocked_read_only_loader() -> None:
    loader = LiveMarketLoader.from_optional_transports(
        dexscreener_transport=lambda _pair_ref: _dex_payload(),
        now=NOW,
    )

    report = build_token_detail(
        pair_ref="solana/PAIR123",
        source="dexscreener",
        loader=loader,
    )

    assert report.status == "OK"
    assert report.identity is not None
    assert report.identity.pair_id == "PAIR123"
    assert report.can_execute_trades is False
    assert report.technical_vector is None
    assert report.technical_vector_status == "UNAVAILABLE"


def test_missing_critical_market_data_returns_insufficient_data() -> None:
    report = build_token_detail(
        fixture=True,
        raw_records=[
            {
                "pair_id": "bad-pair",
                "chain_id": "solana",
                "base_symbol": "BAD",
            }
        ],
    )

    assert report.status == "INSUFFICIENT_DATA"
    assert report.can_execute_trades is False
    assert "MARKET_SOURCE_FIELDS_MISSING" in report.reason_codes


def test_unknown_safety_fields_are_shown_clearly() -> None:
    loader = LiveMarketLoader.from_optional_transports(
        dexscreener_transport=lambda _pair_ref: _dex_payload(),
        now=NOW,
    )

    report = build_token_detail(
        pair_ref="solana/PAIR123",
        source="dexscreener",
        loader=loader,
    )

    assert report.anti_rug.status == "UNKNOWN"
    assert "liquidity_accessible" in report.anti_rug.unknown_fields
    assert "Anti-rug evidence has unknown fields" in report.why_risky


def _dex_payload():
    return {
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": "PAIR123",
                "baseToken": {"symbol": "BONK"},
                "quoteToken": {"symbol": "USDC"},
                "priceUsd": "0.000021",
                "liquidity": {"usd": "2500"},
                "volume": {"h24": "700"},
            }
        ]
    }
