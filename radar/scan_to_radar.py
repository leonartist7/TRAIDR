"""Convert read-only market scan candidates into radar candidates."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from agents.agent_bus import run_agent_bus
from agents.liquidity_agent import LiquidityAgent
from agents.technical_agent import TechnicalAgent
from agents.token_safety_agent import TokenSafetyAgent
from data_pipeline.scan_models import MarketScanCandidate
from radar.models import RadarCandidate
from radar.opportunity_radar import rank_watchlist


def scan_candidates_to_radar(candidates: Iterable[MarketScanCandidate]) -> tuple[RadarCandidate, ...]:
    records = []
    for candidate in candidates:
        if candidate.snapshot is None or candidate.data_quality != "sufficient":
            records.append(
                {
                    "subject_id": candidate.token_pair_id,
                    "analyses": [
                        {
                            "agent": "market_scan",
                            "score": 0,
                            "risk_score": 75,
                            "confidence": 0.0,
                            "status": "INSUFFICIENT_DATA",
                            "reason_codes": list(candidate.reason_codes),
                        }
                    ],
                }
            )
            continue
        records.append(
            {
                "subject_id": candidate.token_pair_id,
                "analyses": run_agent_bus(
                    [TechnicalAgent(), LiquidityAgent(), TokenSafetyAgent()],
                    {
                        "technical_momentum": _momentum_proxy(candidate),
                        "liquidity_usd": float(candidate.liquidity_usd or Decimal("0")),
                        "token_safety_clear": False if _thin_liquidity(candidate) else True,
                    },
                ).analyses,
            }
        )
    return rank_watchlist(records)


def _momentum_proxy(candidate: MarketScanCandidate) -> float:
    volume = candidate.volume_24h_usd or Decimal("0")
    liquidity = candidate.liquidity_usd or Decimal("0")
    if liquidity <= 0:
        return -1.0
    ratio = volume / liquidity
    if ratio >= Decimal("0.25"):
        return 0.7
    if ratio >= Decimal("0.05"):
        return 0.2
    return -0.2


def _thin_liquidity(candidate: MarketScanCandidate) -> bool:
    return (candidate.liquidity_usd or Decimal("0")) < Decimal("1000")
