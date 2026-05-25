"""Sell-risk evaluation for manual portfolio positions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from portfolio.models import ManualPortfolioEntry


class SellRiskState(str, Enum):
    HOLD_POSITION = "HOLD_POSITION"
    REVIEW_POSITION = "REVIEW_POSITION"
    REDUCE_RISK = "REDUCE_RISK"
    EXIT_CANDIDATE = "EXIT_CANDIDATE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class PositionEvidence:
    current_price_usd: Decimal | None = None
    current_liquidity_usd: Decimal | None = None
    previous_liquidity_usd: Decimal | None = None
    risk_score: float | None = None
    previous_risk_score: float | None = None
    radar_state: str | None = None
    previous_radar_state: str | None = None
    opportunity_score: float | None = None
    previous_opportunity_score: float | None = None
    token_safety_complete: bool | None = None
    macro_news_classification: str | None = None


@dataclass(frozen=True)
class SellRiskDecision:
    entry_id: str
    symbol: str
    state: SellRiskState
    reason_codes: tuple[str, ...]
    score: int
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "symbol": self.symbol,
            "state": self.state.value,
            "reason_codes": list(self.reason_codes),
            "score": self.score,
            "can_execute_trades": self.can_execute_trades,
        }


def evaluate_sell_risk(
    entry: ManualPortfolioEntry,
    evidence: PositionEvidence,
    *,
    now: datetime | None = None,
) -> SellRiskDecision:
    reasons: list[str] = ["SELL_RISK_RESEARCH_ONLY", "NO_EXECUTION_ACTION"]
    score = 0
    missing = 0

    if evidence.current_liquidity_usd is None:
        missing += 1
        reasons.append("LIQUIDITY_DATA_MISSING")
    elif _liquidity_drained(evidence.previous_liquidity_usd, evidence.current_liquidity_usd):
        score += 35
        reasons.append("LIQUIDITY_DRAIN")

    if evidence.risk_score is None:
        missing += 1
        reasons.append("RISK_SCORE_MISSING")
    else:
        if evidence.risk_score >= 80:
            score += 35
            reasons.append("RISK_SCORE_HIGH")
        elif evidence.risk_score >= 60:
            score += 20
            reasons.append("RISK_SCORE_ELEVATED")
        if evidence.previous_risk_score is not None and evidence.risk_score - evidence.previous_risk_score >= 15:
            score += 25
            reasons.append("RISK_SCORE_INCREASED")

    if evidence.radar_state is None:
        missing += 1
        reasons.append("RADAR_STATE_MISSING")
    elif evidence.radar_state == "AVOID":
        score += 45
        reasons.append("RADAR_STATE_AVOID")

    if evidence.opportunity_score is None:
        missing += 1
        reasons.append("OPPORTUNITY_SCORE_MISSING")
    elif (
        evidence.previous_opportunity_score is not None
        and evidence.previous_opportunity_score - evidence.opportunity_score >= 25
    ):
        score += 25
        reasons.append("OPPORTUNITY_SCORE_COLLAPSED")

    if evidence.token_safety_complete is not True:
        score += 25
        reasons.append("TOKEN_SAFETY_INCOMPLETE")

    if evidence.macro_news_classification in {"RISK_OFF", "BEARISH_NEWS"}:
        score += 15
        reasons.append("MACRO_NEWS_RISK_OFF")

    if _thesis_stale(entry, now=now):
        score += 15
        reasons.append("THESIS_STALE")

    if _stop_zone_reached(entry, evidence.current_price_usd):
        score += 35
        reasons.append("STOP_ZONE_REACHED")

    if missing >= 3:
        return SellRiskDecision(
            entry.entry_id,
            entry.symbol,
            SellRiskState.INSUFFICIENT_DATA,
            tuple(dict.fromkeys(reasons)),
            score,
        )
    return SellRiskDecision(
        entry.entry_id,
        entry.symbol,
        _state_for_score(score),
        tuple(dict.fromkeys(reasons)),
        score,
    )


def _state_for_score(score: int) -> SellRiskState:
    if score >= 80:
        return SellRiskState.EXIT_CANDIDATE
    if score >= 50:
        return SellRiskState.REDUCE_RISK
    if score >= 20:
        return SellRiskState.REVIEW_POSITION
    return SellRiskState.HOLD_POSITION


def _liquidity_drained(previous: Decimal | None, current: Decimal) -> bool:
    if previous is None or previous <= 0:
        return False
    return (previous - current) / previous >= Decimal("0.30")


def _thesis_stale(entry: ManualPortfolioEntry, *, now: datetime | None) -> bool:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    updated = entry.updated_at
    if updated.tzinfo is None or updated.utcoffset() is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return (current.astimezone(timezone.utc) - updated.astimezone(timezone.utc)).days >= 30


def _stop_zone_reached(entry: ManualPortfolioEntry, current_price: Decimal | None) -> bool:
    if current_price is None or not entry.stop_zone.strip():
        return False
    threshold = _parse_stop_threshold(entry.stop_zone)
    return threshold is not None and current_price <= threshold


def _parse_stop_threshold(stop_zone: str) -> Decimal | None:
    text = stop_zone.strip().lower()
    for prefix in ("below", "<=", "<", "under"):
        if text.startswith(prefix):
            text = text.removeprefix(prefix).strip()
            break
    try:
        return Decimal(text.split()[0])
    except (InvalidOperation, IndexError, ValueError):
        return None
