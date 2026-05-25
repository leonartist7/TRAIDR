"""Exposure analytics for manual portfolio entries."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from portfolio.models import ManualPortfolioEntry, PortfolioReport

_STALE_THESIS_DAYS = 30
_MEME_TAGS = ("meme", "dog", "pepe", "bonk", "shib", "floki")


def build_portfolio_report(
    entries: tuple[ManualPortfolioEntry, ...],
    *,
    now: datetime | None = None,
) -> PortfolioReport:
    active = tuple(entry for entry in entries if entry.active)
    total = sum((entry.size_usd for entry in active), Decimal("0"))
    chain_exposure = _chain_exposure(active)
    warnings = _thesis_warnings(active)
    stale = _stale_thesis_warnings(active, now=now or datetime.now(timezone.utc))
    reasons = ["MANUAL_PORTFOLIO_LOCAL_ONLY", "NO_EXECUTION_ACTION"]
    if not active:
        reasons.append("MANUAL_PORTFOLIO_EMPTY")
    if warnings:
        reasons.append("THESIS_WARNINGS_PRESENT")
    if stale:
        reasons.append("STALE_THESIS_WARNINGS_PRESENT")
    return PortfolioReport(
        total_exposure_usd=total,
        concentration_risk=_concentration_risk(active, total),
        meme_exposure_usd=_meme_exposure(active),
        chain_exposure=chain_exposure,
        thesis_warnings=warnings,
        stale_thesis_warnings=stale,
        entries=active,
        reason_codes=tuple(reasons),
    )


def _concentration_risk(entries: tuple[ManualPortfolioEntry, ...], total: Decimal) -> str:
    if not entries or total <= 0:
        return "none"
    largest = max(entry.size_usd for entry in entries)
    ratio = largest / total
    if ratio >= Decimal("0.60"):
        return "high"
    if ratio >= Decimal("0.35"):
        return "medium"
    return "low"


def _meme_exposure(entries: tuple[ManualPortfolioEntry, ...]) -> Decimal:
    return sum(
        (
            entry.size_usd
            for entry in entries
            if _has_meme_signal(entry)
        ),
        Decimal("0"),
    )


def _chain_exposure(entries: tuple[ManualPortfolioEntry, ...]) -> dict[str, str]:
    totals: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for entry in entries:
        totals[entry.chain] += entry.size_usd
    return {chain: str(amount) for chain, amount in sorted(totals.items())}


def _thesis_warnings(entries: tuple[ManualPortfolioEntry, ...]) -> tuple[str, ...]:
    warnings: list[str] = []
    for entry in entries:
        if not entry.thesis.strip():
            warnings.append(f"{entry.entry_id}:THESIS_MISSING")
        if not entry.stop_zone.strip():
            warnings.append(f"{entry.entry_id}:STOP_ZONE_MISSING")
        if entry.risk_level in {"high", "unknown"} and entry.conviction in {"high", "max"}:
            warnings.append(f"{entry.entry_id}:HIGH_CONVICTION_WITH_HIGH_OR_UNKNOWN_RISK")
    return tuple(warnings)


def _stale_thesis_warnings(
    entries: tuple[ManualPortfolioEntry, ...],
    *,
    now: datetime,
) -> tuple[str, ...]:
    aware_now = _aware(now)
    warnings: list[str] = []
    for entry in entries:
        age_days = (_aware_now_diff(aware_now, entry.updated_at)).days
        if age_days >= _STALE_THESIS_DAYS:
            warnings.append(f"{entry.entry_id}:THESIS_STALE_{age_days}D")
    return tuple(warnings)


def _has_meme_signal(entry: ManualPortfolioEntry) -> bool:
    haystack = " ".join(
        (
            entry.symbol,
            entry.thesis,
            entry.notes,
            entry.pair_ref,
        )
    ).lower()
    return any(tag in haystack for tag in _MEME_TAGS)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _aware_now_diff(now: datetime, then: datetime):
    return now - _aware(then)
