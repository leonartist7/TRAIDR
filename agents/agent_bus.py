"""Structured multi-agent market intelligence bus with no execution authority."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
AnalysisPayload = dict[str, JsonValue]


class MarketIntelligenceAgent(Protocol):
    name: str

    def analyze(self, context: Mapping[str, Any]) -> AnalysisPayload:
        ...


@dataclass(frozen=True)
class AgentBusResult:
    """Structured analysis output from a deterministic local agent run."""

    analyses: tuple[AnalysisPayload, ...]

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "analyses": [dict(analysis) for analysis in self.analyses],
            "agent_count": len(self.analyses),
        }


def make_analysis(
    *,
    agent: str,
    score: float,
    risk_score: float,
    confidence: float,
    status: str,
    reason_codes: Sequence[str],
    summary: str,
) -> AnalysisPayload:
    """Build a JSON-compatible analysis object and clamp numeric fields."""

    return {
        "agent": agent,
        "score": _clamp(score),
        "risk_score": _clamp(risk_score),
        "confidence": _clamp(confidence, low=0.0, high=1.0),
        "status": status,
        "reason_codes": list(reason_codes),
        "summary": summary,
        "can_execute_trades": False,
    }


def insufficient_analysis(agent: str, reason_code: str, summary: str) -> AnalysisPayload:
    """Return a non-bullish insufficient-data analysis."""

    return make_analysis(
        agent=agent,
        score=0.0,
        risk_score=50.0,
        confidence=0.0,
        status="INSUFFICIENT_DATA",
        reason_codes=(reason_code,),
        summary=summary,
    )


def run_agent_bus(
    agents: Iterable[MarketIntelligenceAgent],
    context: Mapping[str, Any],
) -> AgentBusResult:
    """Run deterministic analysis agents and collect structured payloads."""

    analyses = tuple(agent.analyze(context) for agent in agents)
    return AgentBusResult(analyses=analyses)


def numeric(context: Mapping[str, Any], key: str) -> float | None:
    value = context.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def flag(context: Mapping[str, Any], key: str) -> bool | None:
    value = context.get(key)
    return value if isinstance(value, bool) else None


def _clamp(value: float, *, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))
