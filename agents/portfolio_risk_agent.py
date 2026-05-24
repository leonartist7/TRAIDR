"""Portfolio risk scoring agent; no execution authority."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.agent_bus import AnalysisPayload, insufficient_analysis, make_analysis, numeric


class PortfolioRiskAgent:
    name = "portfolio_risk"

    def analyze(self, context: Mapping[str, Any]) -> AnalysisPayload:
        exposure = numeric(context, "portfolio_exposure_usd")
        if exposure is None:
            return insufficient_analysis(self.name, "PORTFOLIO_DATA_MISSING", "portfolio exposure unknown")
        risk = min(100, exposure / 30 * 100)
        return make_analysis(
            agent=self.name,
            score=max(0, 100 - risk),
            risk_score=risk,
            confidence=0.75,
            status="OK",
            reason_codes=("PORTFOLIO_CONTEXT_AVAILABLE",),
            summary="portfolio risk scored from local exposure",
        )
