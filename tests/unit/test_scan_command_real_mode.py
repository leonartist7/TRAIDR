from datetime import datetime, timezone

from cli import commands
from data_pipeline.live_market_loader import LiveMarketLoader


NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_scan_without_source_fails_closed_with_instructions() -> None:
    result = commands.scan(pair_refs=("solana/PAIR123",))

    assert result.exit_code == 0
    assert "SCAN_SOURCE_REQUIRED" in result.output
    assert "--source dexscreener --pair-ref <chain>/<pairAddress>" in result.output


def test_scan_dexscreener_real_mode_uses_mocked_loader(monkeypatch, tmp_path) -> None:
    loader = LiveMarketLoader.from_optional_transports(
        dexscreener_transport=lambda _pair_ref: _dex_response(),
        now=NOW,
    )
    monkeypatch.setattr(commands, "real_dexscreener_loader", lambda: loader)
    database = tmp_path / "dex-scan.duckdb"

    result = commands.scan(
        str(database),
        source="dexscreener",
        pair_refs=("solana/PAIR123",),
    )
    radar = commands.radar(str(database))

    assert result.exit_code == 0
    assert "PAIR123" in result.output
    assert "dexscreener" in result.output
    assert "can_execute_trades" in result.output
    assert "source: scan_evidence" in radar.output
    assert "can_execute_trades" in radar.output


def test_scan_dexscreener_network_failure_fails_closed(monkeypatch) -> None:
    loader = LiveMarketLoader.from_optional_transports(
        dexscreener_transport=lambda _pair_ref: (_ for _ in ()).throw(RuntimeError("offline")),
        now=NOW,
    )
    monkeypatch.setattr(commands, "real_dexscreener_loader", lambda: loader)

    result = commands.scan(source="dexscreener", pair_refs=("solana/PAIR123",))

    assert result.exit_code == 0
    assert "INSUFFICIENT_DATA" in result.output
    assert "DEXSCREENER_TRANSPORT_FAILED" in result.output
    assert "No candidates found." in result.output


def test_discover_dexscreener_real_mode_uses_mocked_transport(monkeypatch) -> None:
    monkeypatch.setattr(
        commands,
        "default_dexscreener_discovery_transport",
        lambda _limit: [
            {
                "chainId": "solana",
                "tokenAddress": "TOKEN123456789",
                "url": "https://dexscreener.com/solana/TOKEN123456789",
            }
        ],
    )

    result = commands.discover(source="dexscreener", limit=20)

    assert result.exit_code == 0
    assert "TOKEN123456789" in result.output
    assert "can_execute_trades" in result.output


def _dex_response():
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
        ],
    }
