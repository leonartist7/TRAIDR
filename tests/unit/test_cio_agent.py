from agents.agent_bus import run_agent_bus
from agents.cio_agent import CIOAgent, CIORecommendation
from agents.liquidity_agent import LiquidityAgent
from agents.news_agent import NewsAgent
from agents.technical_agent import TechnicalAgent
from agents.token_safety_agent import TokenSafetyAgent


def test_cio_high_risk_overrides_high_opportunity() -> None:
    bus = run_agent_bus(
        [TechnicalAgent(), TokenSafetyAgent()],
        {"technical_momentum": 0.9, "token_safety_clear": False},
    )

    decision = CIOAgent().decide(bus.analyses)

    assert decision.recommendation is CIORecommendation.AVOID
    assert "HIGH_RISK_OVERRIDES_OPPORTUNITY" in decision.reason_codes


def test_cio_strong_opportunity_becomes_buy_candidate() -> None:
    bus = run_agent_bus(
        [TechnicalAgent(), LiquidityAgent(), TokenSafetyAgent(), NewsAgent()],
        {
            "technical_momentum": 0.8,
            "liquidity_usd": 25000,
            "token_safety_clear": True,
            "news_sentiment": 0.6,
        },
    )

    decision = CIOAgent().decide(bus.analyses)

    assert decision.recommendation is CIORecommendation.BUY_CANDIDATE
    assert decision.to_dict()["can_execute_trades"] is False


def test_cio_insufficient_data_alerts_instead_of_bullish_output() -> None:
    bus = run_agent_bus([TechnicalAgent(), LiquidityAgent()], {"technical_momentum": 0.8})

    decision = CIOAgent().decide(bus.analyses)

    assert decision.recommendation is CIORecommendation.ALERT
    assert "CONFIDENCE_REDUCED_BY_MISSING_DATA" in decision.reason_codes


def test_cio_conflicting_agents_alert_when_risk_not_avoid_level() -> None:
    decision = CIOAgent().decide(
        [
            {"agent": "technical", "score": 90, "risk_score": 10, "confidence": 0.8, "status": "OK"},
            {"agent": "liquidity", "score": 30, "risk_score": 70, "confidence": 0.8, "status": "OK"},
        ]
    )

    assert decision.recommendation is CIORecommendation.ALERT
    assert "CONFLICTING_AGENT_SIGNALS" in decision.reason_codes
