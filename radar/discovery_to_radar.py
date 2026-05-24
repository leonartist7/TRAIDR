"""Convert token discovery candidates into conservative radar candidates."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from agents.agent_bus import run_agent_bus
from agents.liquidity_agent import LiquidityAgent
from agents.technical_agent import TechnicalAgent
from agents.token_safety_agent import TokenSafetyAgent
from data_pipeline.discovery_models import DiscoveryCandidate
from radar.models import RadarCandidate
from radar.opportunity_radar import rank_watchlist


def discovery_candidates_to_radar(candidates: Iterable[DiscoveryCandidate]) -> tuple[RadarCandidate, ...]:
    records = []
    for candidate in candidates:
        if candidate.missing_metric_count >= 2:
            records.append(
                {
                    "subject_id": candidate.pair_id,
                    "analyses": [
                        {
                            "agent": "token_discovery",
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
                "subject_id": candidate.pair_id,
                "analyses": run_agent_bus(
                    [TechnicalAgent(), LiquidityAgent(), TokenSafetyAgent()],
                    {
                        "technical_momentum": _momentum_proxy(candidate),
                        "liquidity_usd": float(candidate.liquidity_usd or Decimal("0")),
                        "token_safety_clear": True if candidate.missing_metric_count == 0 else False,
                    },
                ).analyses,
            }
        )
    return rank_watchlist(records)


def _momentum_proxy(candidate: DiscoveryCandidate) -> float:
    volume = candidate.volume_24h_usd or Decimal("0")
    liquidity = candidate.liquidity_usd or Decimal("0")
    if liquidity <= 0:
        return -0.6
    ratio = volume / liquidity
    if ratio >= Decimal("0.25"):
        return 0.45
    if ratio >= Decimal("0.05"):
        return 0.1
    return -0.2
