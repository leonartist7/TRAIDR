from agents.agent_bus import run_agent_bus
from agents.liquidity_agent import LiquidityAgent
from agents.token_safety_agent import TokenSafetyAgent
from agents.technical_agent import TechnicalAgent


def test_agent_bus_returns_structured_json_compatible_analyses() -> None:
    result = run_agent_bus(
        [TechnicalAgent(), LiquidityAgent(), TokenSafetyAgent()],
        {
            "technical_momentum": 0.5,
            "liquidity_usd": 12000,
            "token_safety_clear": True,
        },
    )

    payload = result.to_dict()
    assert payload["agent_count"] == 3
    assert all(analysis["can_execute_trades"] is False for analysis in payload["analyses"])
    assert {analysis["agent"] for analysis in payload["analyses"]} == {
        "technical",
        "liquidity",
        "token_safety",
    }


def test_agent_bus_missing_critical_data_returns_non_bullish_analysis() -> None:
    result = run_agent_bus([TechnicalAgent()], {})
    analysis = result.analyses[0]

    assert analysis["status"] == "INSUFFICIENT_DATA"
    assert analysis["score"] == 0.0
    assert analysis["confidence"] == 0.0
