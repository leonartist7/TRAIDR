"""Build read-only token detail reports from existing safe data boundaries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from data_pipeline.live_market_loader import LiveMarketLoader
from data_pipeline.market_scan import FIXTURE_MARKET_RECORDS, real_dexscreener_loader, scan_markets
from data_pipeline.scan_models import MarketScanCandidate
from radar.models import RadarCandidate
from radar.scan_to_radar import scan_candidates_to_radar
from risk.anti_rug import assess_anti_rug
from risk.models import AntiRugEvidence
from storage.repositories import ResearchRepository
from technicals.vector_engine import RawCandle, build_technical_vector
from token_detail.detail_models import AntiRugDetailStatus, TokenDetailReport, TokenIdentity


SAFE_FIXTURE_ANTI_RUG = AntiRugEvidence(
    liquidity_accessible=True,
    liquidity_meets_floor=True,
    liquidity_status_known=True,
    mint_freeze_or_sell_restriction=False,
    unsafe_holder_or_creator_control=False,
    honeypot_tax_route_or_sellability_issue=False,
    identity_ambiguous=False,
    evidence_complete=True,
)

UNKNOWN_ANTI_RUG = AntiRugEvidence(
    liquidity_accessible=None,
    liquidity_meets_floor=None,
    liquidity_status_known=None,
    mint_freeze_or_sell_restriction=None,
    unsafe_holder_or_creator_control=None,
    honeypot_tax_route_or_sellability_issue=None,
    identity_ambiguous=None,
    evidence_complete=None,
)


def build_token_detail(
    *,
    fixture: bool = False,
    pair_ref: str | None = None,
    source: str | None = None,
    loader: LiveMarketLoader | None = None,
    raw_records: Iterable[Mapping[str, Any]] | None = None,
    candles: Sequence[RawCandle] | None = None,
    anti_rug: AntiRugEvidence | None = None,
    repository: ResearchRepository | None = None,
) -> TokenDetailReport:
    """Create a local research card; never creates executable instructions."""

    if fixture:
        scan_result = scan_markets(fixture=True, raw_records=raw_records, repository=repository)
        selected = _select_candidate(scan_result.candidates, pair_ref)
        evidence = anti_rug or SAFE_FIXTURE_ANTI_RUG
        vector_candles = candles if candles is not None else _fixture_candles(selected)
    elif source == "dexscreener" and pair_ref:
        scan_result = scan_markets(
            pair_refs=(pair_ref,),
            source_names=("dexscreener",),
            loader=loader or real_dexscreener_loader(),
            repository=repository,
        )
        selected = _select_candidate(scan_result.candidates, pair_ref)
        evidence = anti_rug or UNKNOWN_ANTI_RUG
        vector_candles = candles
    else:
        return _insufficient_report("TOKEN_DETAIL_SOURCE_REQUIRED")

    if selected is None:
        return _insufficient_report(*scan_result.reason_codes)
    if _critical_market_data_missing(selected):
        return _candidate_insufficient_report(selected, "TOKEN_DETAIL_CRITICAL_DATA_MISSING")

    radar = _first_radar(selected)
    vector_result = build_technical_vector(pair_id=selected.token_pair_id, candles=vector_candles)
    technical_vector = vector_result.value if vector_result.ok and vector_result.value is not None else None
    technical_status = "OK" if technical_vector is not None else "UNAVAILABLE"
    anti_rug_status = _anti_rug_status(evidence)
    reasons = _reason_codes(
        selected.reason_codes,
        radar.reason_codes if radar else (),
        vector_result.reason_codes if not vector_result.ok else ("TECHNICAL_VECTOR_AVAILABLE",),
        (anti_rug_status.status,),
    )
    return TokenDetailReport(
        status="OK",
        identity=_identity(selected),
        price_usd=selected.price_usd,
        liquidity_usd=selected.liquidity_usd,
        volume_24h_usd=selected.volume_24h_usd,
        technical_vector=technical_vector,
        technical_vector_status=technical_status,
        liquidity_score=_liquidity_score(selected.liquidity_usd),
        opportunity_score=radar.opportunity_score if radar else 0.0,
        risk_score=radar.risk_score if radar else 100.0,
        anti_rug=anti_rug_status,
        radar_state=radar.state.value if radar else "AVOID",
        reason_codes=reasons,
        why_interesting=_why_interesting(selected, radar, technical_vector),
        why_risky=_why_risky(selected, anti_rug_status, radar),
    )


def _select_candidate(
    candidates: Iterable[MarketScanCandidate],
    pair_ref: str | None,
) -> MarketScanCandidate | None:
    items = tuple(candidates)
    if not items:
        return None
    if pair_ref is None:
        return items[0]
    pair_leaf = pair_ref.split("/", 1)[-1]
    for candidate in items:
        if candidate.token_pair_id == pair_ref or candidate.token_pair_id == pair_leaf:
            return candidate
    return items[0]


def _critical_market_data_missing(candidate: MarketScanCandidate) -> bool:
    return (
        candidate.snapshot is None
        or candidate.data_quality != "sufficient"
        or candidate.price_usd is None
        or candidate.liquidity_usd is None
        or candidate.volume_24h_usd is None
    )


def _first_radar(candidate: MarketScanCandidate) -> RadarCandidate | None:
    radar = scan_candidates_to_radar((candidate,))
    return radar[0] if radar else None


def _identity(candidate: MarketScanCandidate) -> TokenIdentity:
    if candidate.snapshot is not None:
        return TokenIdentity(
            pair_id=candidate.snapshot.identity.pair_id,
            chain=candidate.snapshot.identity.chain_id,
            base_symbol=candidate.snapshot.identity.base_symbol,
            quote_symbol=candidate.snapshot.identity.quote_symbol,
            source=candidate.source,
        )
    return TokenIdentity(
        pair_id=candidate.token_pair_id,
        chain="unknown",
        base_symbol="unknown",
        quote_symbol="unknown",
        source=candidate.source,
    )


def _anti_rug_status(evidence: AntiRugEvidence) -> AntiRugDetailStatus:
    assessment = assess_anti_rug(evidence)
    unknown_fields = tuple(
        field
        for field in evidence.__dataclass_fields__
        if getattr(evidence, field) is None
    )
    if assessment.hard_failed:
        status = "HARD_FAIL"
    elif assessment.insufficient_data:
        status = "UNKNOWN"
    else:
        status = "CLEAR"
    return AntiRugDetailStatus(
        status=status,
        unknown_fields=unknown_fields,
        hard_fail_reasons=assessment.hard_fail_reasons,
        insufficient_data_reasons=assessment.insufficient_data_reasons,
    )


def _liquidity_score(liquidity_usd: Decimal | None) -> float:
    if liquidity_usd is None:
        return 0.0
    if liquidity_usd >= Decimal("10000"):
        return 85.0
    if liquidity_usd >= Decimal("2500"):
        return 60.0
    if liquidity_usd >= Decimal("1000"):
        return 40.0
    return 15.0


def _fixture_candles(candidate: MarketScanCandidate | None) -> tuple[dict[str, str], ...] | None:
    if candidate is None or candidate.price_usd is None:
        return None
    close = candidate.price_usd
    start = close * Decimal("0.94")
    mid = close * Decimal("0.98")
    return (
        _candle("2026-05-22T11:45:00+00:00", start, close * Decimal("0.96"), start * Decimal("0.98"), start, "900"),
        _candle("2026-05-22T11:50:00+00:00", start, mid, start * Decimal("0.99"), mid, "950"),
        _candle("2026-05-22T11:55:00+00:00", mid, close * Decimal("1.02"), mid * Decimal("0.99"), close, "1150"),
    )


def _candle(timestamp: str, open_: Decimal, high: Decimal, low: Decimal, close: Decimal, volume: str) -> dict[str, str]:
    return {
        "timestamp": timestamp,
        "open": str(open_),
        "high": str(high),
        "low": str(low),
        "close": str(close),
        "volume": volume,
    }


def _why_interesting(
    candidate: MarketScanCandidate,
    radar: RadarCandidate | None,
    technical_vector: Mapping[str, Any] | None,
) -> str:
    pieces = [
        f"{candidate.token_pair_id} has read-only market data from {candidate.source}.",
        f"Liquidity score is {_liquidity_score(candidate.liquidity_usd):.0f}/100.",
    ]
    if radar is not None:
        pieces.append(f"Radar classifies it as {radar.state.value} with opportunity score {radar.opportunity_score:.1f}.")
    if technical_vector is not None:
        pieces.append("A compact local technical vector is available for review.")
    return " ".join(pieces)


def _why_risky(
    candidate: MarketScanCandidate,
    anti_rug: AntiRugDetailStatus,
    radar: RadarCandidate | None,
) -> str:
    pieces: list[str] = []
    if candidate.liquidity_usd is not None and candidate.liquidity_usd < Decimal("2500"):
        pieces.append("Liquidity is thin for micro-cap research.")
    if anti_rug.status == "UNKNOWN":
        pieces.append("Anti-rug evidence has unknown fields and is not a safety approval.")
    elif anti_rug.status == "HARD_FAIL":
        pieces.append("Anti-rug evidence contains hard-fail reasons.")
    if radar is not None and radar.risk_score >= 50:
        pieces.append(f"Radar risk score is elevated at {radar.risk_score:.1f}.")
    if not pieces:
        pieces.append("This is still research-only and cannot execute trades.")
    return " ".join(pieces)


def _candidate_insufficient_report(candidate: MarketScanCandidate, *reason_codes: str) -> TokenDetailReport:
    anti_rug = _anti_rug_status(UNKNOWN_ANTI_RUG)
    return TokenDetailReport(
        status="INSUFFICIENT_DATA",
        identity=_identity(candidate),
        price_usd=candidate.price_usd,
        liquidity_usd=candidate.liquidity_usd,
        volume_24h_usd=candidate.volume_24h_usd,
        technical_vector=None,
        technical_vector_status="UNAVAILABLE",
        liquidity_score=_liquidity_score(candidate.liquidity_usd),
        opportunity_score=0.0,
        risk_score=100.0,
        anti_rug=anti_rug,
        radar_state="AVOID",
        reason_codes=_reason_codes(candidate.reason_codes, reason_codes),
        why_interesting="Critical market data is missing, so there is no actionable research edge.",
        why_risky="Missing or insufficient data prevents a reliable local token detail report.",
    )


def _insufficient_report(*reason_codes: str) -> TokenDetailReport:
    anti_rug = _anti_rug_status(UNKNOWN_ANTI_RUG)
    return TokenDetailReport(
        status="INSUFFICIENT_DATA",
        identity=None,
        price_usd=None,
        liquidity_usd=None,
        volume_24h_usd=None,
        technical_vector=None,
        technical_vector_status="UNAVAILABLE",
        liquidity_score=0.0,
        opportunity_score=0.0,
        risk_score=100.0,
        anti_rug=anti_rug,
        radar_state="AVOID",
        reason_codes=_reason_codes(reason_codes),
        why_interesting="No reliable token detail source was available.",
        why_risky="TRAIDR fails closed when token detail inputs are missing.",
    )


def _reason_codes(*groups: Iterable[str]) -> tuple[str, ...]:
    reasons: list[str] = ["TOKEN_DETAIL_READ_ONLY"]
    for group in groups:
        reasons.extend(str(reason) for reason in group if reason)
    return tuple(dict.fromkeys(reasons))


__all__ = [
    "FIXTURE_MARKET_RECORDS",
    "SAFE_FIXTURE_ANTI_RUG",
    "UNKNOWN_ANTI_RUG",
    "build_token_detail",
]
