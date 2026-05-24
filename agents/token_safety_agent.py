"""Token safety scoring agent that treats unknown safety as non-bullish."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.agent_bus import AnalysisPayload, flag, insufficient_analysis, make_analysis


class TokenSafetyAgent:
    name = "token_safety"

    def analyze(self, context: Mapping[str, Any]) -> AnalysisPayload:
        safe = flag(context, "token_safety_clear")
        if safe is None:
            return insufficient_analysis(self.name, "TOKEN_SAFETY_UNKNOWN", "token safety evidence incomplete")
        if not safe:
            return make_analysis(
                agent=self.name,
                score=0,
                risk_score=95,
                confidence=0.9,
                status="HIGH_RISK",
                reason_codes=("TOKEN_SAFETY_HARD_FAIL",),
                summary="token safety signal is high risk",
            )
        return make_analysis(
            agent=self.name,
            score=70,
            risk_score=10,
            confidence=0.8,
            status="OK",
            reason_codes=("TOKEN_SAFETY_CLEAR",),
            summary="token safety evidence is clear",
        )
