"""On-chain activity scoring agent; no live RPC or execution behavior."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.agent_bus import AnalysisPayload, insufficient_analysis, make_analysis, numeric


class OnchainAgent:
    name = "onchain"

    def analyze(self, context: Mapping[str, Any]) -> AnalysisPayload:
        activity = numeric(context, "onchain_activity_score")
        if activity is None:
            return insufficient_analysis(self.name, "ONCHAIN_DATA_MISSING", "on-chain activity unknown")
        return make_analysis(
            agent=self.name,
            score=activity,
            risk_score=max(0, 50 - activity / 2),
            confidence=0.7,
            status="OK",
            reason_codes=("ONCHAIN_ACTIVITY_AVAILABLE",),
            summary="on-chain activity scored from fixture context",
        )
