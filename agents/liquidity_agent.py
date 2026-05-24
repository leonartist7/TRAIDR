"""Liquidity scoring agent that penalizes thin-liquidity contexts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.agent_bus import AnalysisPayload, insufficient_analysis, make_analysis, numeric


class LiquidityAgent:
    name = "liquidity"

    def analyze(self, context: Mapping[str, Any]) -> AnalysisPayload:
        liquidity = numeric(context, "liquidity_usd")
        if liquidity is None:
            return insufficient_analysis(self.name, "LIQUIDITY_DATA_MISSING", "liquidity unknown")
        if liquidity < 1000:
            score = 5
            risk = 90
            reason = "LIQUIDITY_CRITICAL"
        elif liquidity < 10000:
            score = 35
            risk = 65
            reason = "LIQUIDITY_THIN"
        else:
            score = 75
            risk = 20
            reason = "LIQUIDITY_ACCEPTABLE"
        return make_analysis(
            agent=self.name,
            score=score,
            risk_score=risk,
            confidence=0.8,
            status="OK",
            reason_codes=(reason,),
            summary="liquidity scored from local market context",
        )
