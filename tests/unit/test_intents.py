import json

from agents.intents import BoundedIntentAction, parse_intent
from utils.results import ResultStatus


def test_valid_hold_intent_parses_strictly() -> None:
    result = parse_intent(
        json.dumps(
            {
                "intent": "HOLD",
                "confidence": "unknown",
                "reason_codes": ["WAIT"],
                "evidence_summary": ["bounded hold"],
                "risk_handoff_required": True,
            }
        )
    )

    assert result.ok is True
    assert result.value is not None
    assert result.value.action is BoundedIntentAction.HOLD


def test_invalid_json_and_extra_fields_are_non_actionable() -> None:
    malformed = parse_intent("{not json")
    extra = parse_intent(
        json.dumps(
            {
                "intent": "HOLD",
                "confidence": "unknown",
                "reason_codes": ["WAIT"],
                "evidence_summary": ["bounded hold"],
                "risk_handoff_required": True,
                "execute": "now",
            }
        )
    )

    assert malformed.status is ResultStatus.HOLD
    assert malformed.reason_codes == ("LLM_OUTPUT_INVALID_JSON",)
    assert extra.reason_codes == ("LLM_OUTPUT_EXTRA_FIELDS",)

