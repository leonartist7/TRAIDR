"""Read-only market scan orchestration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from data_pipeline.contracts import AdapterResult, NormalizedMarketSnapshot
from data_pipeline.dexscreener_adapter import DexScreenerAdapter, default_dexscreener_transport
from data_pipeline.live_market_loader import LiveMarketLoader
from data_pipeline.normalization import normalize_market_record
from data_pipeline.scan_models import MarketScanCandidate, MarketScanResult
from storage.repositories import ResearchRepository


FIXTURE_MARKET_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "pair_id": "fixture-sol-usdc",
        "chain_id": "solana",
        "base_symbol": "SOL",
        "quote_symbol": "USDC",
        "price_usd": "4.20",
        "liquidity_usd": "12000",
        "volume_24h_usd": "3000",
        "observed_at": "2026-05-22T11:59:00+00:00",
        "source_record_id": "fixture-scan-sol-usdc",
        "raw_status": "fixture",
    },
    {
        "pair_id": "fixture-bonk-usdc",
        "chain_id": "solana",
        "base_symbol": "BONK",
        "quote_symbol": "USDC",
        "price_usd": "0.000021",
        "liquidity_usd": "2500",
        "volume_24h_usd": "700",
        "observed_at": "2026-05-22T11:58:00+00:00",
        "source_record_id": "fixture-scan-bonk-usdc",
        "raw_status": "fixture",
    },
)

FIXTURE_NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def scan_markets(
    *,
    fixture: bool = False,
    pair_refs: Iterable[str] = (),
    source_names: Iterable[str] = ("dexscreener", "coingecko", "defillama"),
    loader: LiveMarketLoader | None = None,
    raw_records: Iterable[Mapping[str, Any]] | None = None,
    now: datetime | None = None,
    repository: ResearchRepository | None = None,
) -> MarketScanResult:
    """Scan market data through read-only adapter boundaries."""

    scan_now = now or datetime.now(timezone.utc)
    if fixture:
        return _scan_raw_records(
            raw_records or FIXTURE_MARKET_RECORDS,
            source_name="fixture_scan",
            now=FIXTURE_NOW,
            repository=repository,
        )

    if raw_records is not None:
        return _scan_raw_records(
            raw_records,
            source_name="raw_scan",
            now=scan_now,
            repository=repository,
        )

    refs = tuple(pair_refs)
    if not refs:
        return MarketScanResult("INSUFFICIENT_DATA", (), ("SCAN_PAIR_REFS_MISSING",))

    market_loader = loader or LiveMarketLoader()
    candidates: list[MarketScanCandidate] = []
    reasons: list[str] = []
    for pair_ref in refs:
        result = market_loader.first_available(pair_ref, source_names)
        if result.ok and result.value is not None:
            candidate = MarketScanCandidate.from_snapshot(result.value)
            candidates.append(candidate)
            _store_candidate(repository, candidate)
        else:
            reasons.extend(result.reason_codes)
    if not candidates:
        return MarketScanResult("INSUFFICIENT_DATA", (), tuple(dict.fromkeys(reasons or ["SCAN_NO_CANDIDATES"])))
    return MarketScanResult("OK", tuple(candidates), ("SCAN_CANDIDATES_AVAILABLE",))


def fixture_loader(now: datetime | None = None) -> LiveMarketLoader:
    records = {record["pair_id"]: record for record in FIXTURE_MARKET_RECORDS}

    def transport(pair_ref: str) -> Mapping[str, Any] | None:
        return records.get(pair_ref)

    return LiveMarketLoader.from_optional_transports(
        now=now or FIXTURE_NOW,
        coingecko_transport=transport,
        defillama_transport=transport,
    )


def dexscreener_loader(transport, *, now: datetime | None = None) -> LiveMarketLoader:
    from data_pipeline.source_registry import SourceRegistry

    registry = SourceRegistry()
    registry.register(DexScreenerAdapter(transport, now=now))
    return LiveMarketLoader(registry)


def real_dexscreener_loader(*, now: datetime | None = None) -> LiveMarketLoader:
    return dexscreener_loader(default_dexscreener_transport, now=now)


def _scan_raw_records(
    records: Iterable[Mapping[str, Any]],
    *,
    source_name: str,
    now: datetime,
    repository: ResearchRepository | None,
) -> MarketScanResult:
    candidates: list[MarketScanCandidate] = []
    reasons: list[str] = []
    for record in records:
        normalized = normalize_market_record(record, source_name=source_name, now=now)
        if normalized.ok and normalized.value is not None:
            candidate = MarketScanCandidate.from_snapshot(normalized.value)
            candidates.append(candidate)
            _store_candidate(repository, candidate)
        else:
            reasons.extend(normalized.reason_codes)
    if not candidates:
        return MarketScanResult("INSUFFICIENT_DATA", (), tuple(dict.fromkeys(reasons or ["SCAN_NO_CANDIDATES"])))
    return MarketScanResult("OK", tuple(candidates), ("SCAN_CANDIDATES_AVAILABLE",))


def _store_candidate(repository: ResearchRepository | None, candidate: MarketScanCandidate) -> None:
    if repository is None:
        return
    payload = candidate.to_dict()
    payload["pair_id"] = payload.pop("token_pair_id")
    repository.record_evidence(
        source_name=f"market_scan:{candidate.source}",
        observed_at=candidate.observed_at,
        quality_status=candidate.data_quality,
        payload=payload,
        provenance={
            "source": candidate.source,
            "pair_id": candidate.token_pair_id,
            "read_only": True,
            "can_execute_trades": False,
        },
    )
