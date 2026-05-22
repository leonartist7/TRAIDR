import json

from agents.llm_gateway import MockResearchGateway


def test_mock_gateway_defaults_to_hold() -> None:
    gateway = MockResearchGateway()

    output = json.loads(gateway.complete(system_prompt="safe", payload_toon="pair: fixture"))

    assert output["intent"] == "HOLD"
    assert output["risk_handoff_required"] is True
    assert gateway.calls == [("safe", "pair: fixture")]

