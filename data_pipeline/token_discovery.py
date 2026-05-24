"""Read-only token discovery from fixture or public source payloads."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from data_pipeline.discovery_models import DiscoveryCandidate, TokenDiscoveryResult
from storage.repositories import ResearchRepository

DiscoveryTransport = Callable[[int], Mapping[str, Any] | Iterable[Mapping[str, Any]] | None]
DEXSCREENER_PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"

FIXTURE_DISCOVERY_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "pair_id": "fixture-sol-usdc",
        "chain": "solana",
        "base_symbol": "SOL",
        "quote_symbol": "USDC",
        "price_usd": "4.20",
        "liquidity_usd": "12000",
        "volume_24h_usd": "3000",
        "source": "fixture_discovery",
        "observed_at": "2026-05-22T11:59:00+00:00",
    },
    {
        "pair_id": "fixture-new-usdc",
        "chain": "solana",
        "base_symbol": "NEW",
        "quote_symbol": "USDC",
        "price_usd": None,
        "liquidity_usd": "450",
        "volume_24h_usd": None,
        "source": "fixture_discovery",
        "observed_at": "2026-05-22T11:58:00+00:00",
    },
)


def discover_tokens(
    *,
    fixture: bool = False,
    source: str | None = None,
    limit: int = 20,
    transport: DiscoveryTransport | None = None,
    raw_records: Iterable[Mapping[str, Any]] | None = None,
    repository: ResearchRepository | None = None,
    now: datetime | None = None,
) -> TokenDiscoveryResult:
    observed_now = now or datetime.now(timezone.utc)
    if fixture:
        return _discover_from_records(
            raw_records or FIXTURE_DISCOVERY_RECORDS,
            limit=limit,
            default_source="fixture_discovery",
            repository=repository,
        )
    if source != "dexscreener":
        return TokenDiscoveryResult(
            "INSUFFICIENT_DATA",
            (),
            ("DISCOVERY_SOURCE_REQUIRED",),
        )
    if transport is None:
        return TokenDiscoveryResult(
            "INSUFFICIENT_DATA",
            (),
            ("DISCOVERY_TRANSPORT_UNAVAILABLE",),
        )
    try:
        payload = transport(limit)
    except Exception:
        return TokenDiscoveryResult(
            "INSUFFICIENT_DATA",
            (),
            ("DISCOVERY_TRANSPORT_FAILED",),
        )
    if payload is None:
        return TokenDiscoveryResult("INSUFFICIENT_DATA", (), ("DISCOVERY_SOURCE_MISSING",))
    records = _extract_dexscreener_records(payload, observed_now=observed_now)
    return _discover_from_records(
        records,
        limit=limit,
        default_source="dexscreener",
        repository=repository,
    )


def _discover_from_records(
    records: Iterable[Mapping[str, Any]],
    *,
    limit: int,
    default_source: str,
    repository: ResearchRepository | None,
) -> TokenDiscoveryResult:
    candidates: list[DiscoveryCandidate] = []
    reasons: list[str] = []
    for record in records:
        if len(candidates) >= limit:
            break
        candidate = _candidate_from_record(record, default_source=default_source)
        if candidate is None:
            reasons.append("DISCOVERY_RECORD_MALFORMED")
            continue
        candidates.append(candidate)
        _store_candidate(repository, candidate)
    if not candidates:
        return TokenDiscoveryResult(
            "INSUFFICIENT_DATA",
            (),
            tuple(dict.fromkeys(reasons or ["DISCOVERY_NO_CANDIDATES"])),
        )
    return TokenDiscoveryResult("OK", tuple(candidates), ("DISCOVERY_CANDIDATES_AVAILABLE",))


def default_dexscreener_discovery_transport(limit: int) -> Iterable[Mapping[str, Any]]:
    """Fetch latest DexScreener token profiles as read-only discovery candidates."""

    request = Request(
        DEXSCREENER_PROFILES_URL,
        headers={"User-Agent": "TRAIDR-read-only-discovery/0.1"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=10) as response:
            status = getattr(response, "status", 200)
            if status >= 400:
                raise RuntimeError(f"DexScreener HTTP status {status}")
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("DexScreener discovery request failed") from exc
    if isinstance(payload, list):
        return payload[:limit]
    if isinstance(payload, Mapping):
        profiles = payload.get("profiles") or payload.get("pairs") or []
        if isinstance(profiles, list):
            return profiles[:limit]
    return ()


def _extract_dexscreener_records(
    payload: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    *,
    observed_now: datetime,
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(payload, Mapping):
        raw_pairs = payload.get("pairs")
        if raw_pairs is None and "pairAddress" in payload:
            raw_pairs = [payload]
    else:
        raw_pairs = payload
    records: list[Mapping[str, Any]] = []
    for pair in raw_pairs or ():
        if not isinstance(pair, Mapping):
            continue
        base_token = _mapping(pair.get("baseToken"))
        quote_token = _mapping(pair.get("quoteToken"))
        liquidity = _mapping(pair.get("liquidity"))
        volume = _mapping(pair.get("volume"))
        records.append(
            {
                "pair_id": pair.get("pairAddress") or _profile_pair_id(pair),
                "chain": pair.get("chainId"),
                "base_symbol": base_token.get("symbol") or _token_symbol_fallback(pair),
                "quote_symbol": quote_token.get("symbol") or "UNKNOWN",
                "price_usd": pair.get("priceUsd"),
                "liquidity_usd": liquidity.get("usd"),
                "volume_24h_usd": volume.get("h24"),
                "source": "dexscreener",
                "observed_at": pair.get("observed_at") or observed_now.isoformat(),
            }
        )
    return tuple(records)


def _candidate_from_record(
    record: Mapping[str, Any],
    *,
    default_source: str,
) -> DiscoveryCandidate | None:
    try:
        pair_id = _text(record.get("pair_id"))
        chain = _text(record.get("chain"))
        base_symbol = _text(record.get("base_symbol"))
        quote_symbol = _text(record.get("quote_symbol"))
        observed_at = _datetime(record.get("observed_at"))
    except (TypeError, ValueError):
        return None
    price = _decimal_or_none(record.get("price_usd"))
    liquidity = _decimal_or_none(record.get("liquidity_usd"))
    volume = _decimal_or_none(record.get("volume_24h_usd"))
    reasons = ["DISCOVERY_CANDIDATE_READ_ONLY"]
    missing = sum(value is None for value in (price, liquidity, volume))
    if missing:
        reasons.append("DISCOVERY_MARKET_DATA_PARTIAL")
    if missing >= 2:
        reasons.append("DISCOVERY_HIGH_MISSING_DATA")
    return DiscoveryCandidate(
        pair_id=pair_id,
        chain=chain,
        base_symbol=base_symbol,
        quote_symbol=quote_symbol,
        price_usd=price,
        liquidity_usd=liquidity,
        volume_24h_usd=volume,
        source=str(record.get("source") or default_source),
        observed_at=observed_at,
        reason_codes=tuple(reasons),
    )


def _store_candidate(repository: ResearchRepository | None, candidate: DiscoveryCandidate) -> None:
    if repository is None:
        return
    repository.record_evidence(
        source_name=f"token_discovery:{candidate.source}",
        observed_at=candidate.observed_at,
        quality_status="partial" if candidate.missing_metric_count else "sufficient",
        payload=candidate.to_dict(),
        provenance={
            "source": candidate.source,
            "pair_id": candidate.pair_id,
            "read_only": True,
            "can_execute_trades": False,
        },
    )


def _text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty discovery text field")
    return text


def _datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _profile_pair_id(pair: Mapping[str, Any]) -> str | None:
    chain = pair.get("chainId")
    token = pair.get("tokenAddress")
    if chain and token:
        return f"{chain}/{token}"
    return None


def _token_symbol_fallback(pair: Mapping[str, Any]) -> str | None:
    token = pair.get("tokenAddress")
    if token:
        return str(token)[:8].upper()
    return None
