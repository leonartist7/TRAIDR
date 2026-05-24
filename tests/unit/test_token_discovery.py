from datetime import datetime, timezone

from data_pipeline.token_discovery import default_dexscreener_discovery_transport, discover_tokens
from storage.duckdb_store import DuckDBStore
from storage.repositories import ResearchRepository
from storage.schema import initialize_schema


NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_fixture_discovery_returns_research_only_candidates() -> None:
    result = discover_tokens(fixture=True)

    assert result.status == "OK"
    assert result.can_execute_trades is False
    assert result.candidates
    assert result.candidates[0].pair_id == "fixture-sol-usdc"
    assert result.candidates[0].can_execute_trades is False


def test_real_discovery_transport_failure_returns_insufficient_data() -> None:
    result = discover_tokens(
        source="dexscreener",
        transport=lambda _limit: (_ for _ in ()).throw(RuntimeError("offline")),
        now=NOW,
    )

    assert result.status == "INSUFFICIENT_DATA"
    assert result.candidates == ()
    assert "DISCOVERY_TRANSPORT_FAILED" in result.reason_codes


def test_dexscreener_discovery_shape_normalizes() -> None:
    result = discover_tokens(
        source="dexscreener",
        transport=lambda _limit: _dex_payload(),
        now=NOW,
    )

    assert result.status == "OK"
    assert result.candidates[0].pair_id == "PAIR123"
    assert result.candidates[0].source == "dexscreener"
    assert result.candidates[0].price_usd is not None


def test_dexscreener_profile_shape_normalizes_with_missing_metrics() -> None:
    result = discover_tokens(
        source="dexscreener",
        transport=lambda _limit: [
            {
                "chainId": "solana",
                "tokenAddress": "TOKEN123456789",
                "url": "https://dexscreener.com/solana/TOKEN123456789",
            }
        ],
        now=NOW,
    )

    assert result.status == "OK"
    assert result.candidates[0].pair_id == "solana/TOKEN123456789"
    assert result.candidates[0].base_symbol == "TOKEN123"
    assert result.candidates[0].missing_metric_count == 3


def test_default_dexscreener_discovery_transport_uses_profiles_endpoint(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_exc_info):
            return None

        def read(self):
            return b'[{"chainId":"solana","tokenAddress":"TOKEN123"}]'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("data_pipeline.token_discovery.urlopen", fake_urlopen)

    payload = tuple(default_dexscreener_discovery_transport(20))

    assert payload[0]["tokenAddress"] == "TOKEN123"
    assert captured["url"].endswith("/token-profiles/latest/v1")
    assert captured["timeout"] == 10


def test_discovery_persists_evidence(tmp_path) -> None:
    database = tmp_path / "discovery.duckdb"
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        repository = ResearchRepository(store.connection)
        result = discover_tokens(fixture=True, repository=repository)
        count = store.connection.execute(
            "SELECT COUNT(*) FROM evidence_snapshots WHERE source_name LIKE 'token_discovery:%'"
        ).fetchone()[0]

    assert result.status == "OK"
    assert count == len(result.candidates)


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
