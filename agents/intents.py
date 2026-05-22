"""Strict bounded research intent parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from risk.models import IntentAction, SignalConfidence
from utils.results import Result

_ALLOWED_FIELDS = {
    "intent",
    "confidence",
    "reason_codes",
    "evidence_summary",
    "risk_handoff_required",
    "requested_notional_usd",
}
_REQUIRED_FIELDS = {
    "intent",
    "confidence",
    "reason_codes",
    "evidence_summary",
    "risk_handoff_required",
}


class BoundedIntentAction(str, Enum):
    HOLD = "HOLD"
    BUY = "BUY"
    SELL = "SELL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class BoundedIntent:
    action: BoundedIntentAction
    confidence: SignalConfidence
    reason_codes: tuple[str, ...]
    evidence_summary: tuple[str, ...]
    requested_notional_usd: Decimal = Decimal("0")

    def risk_action(self) -> IntentAction:
        if self.action in (BoundedIntentAction.BUY, BoundedIntentAction.SELL):
            return IntentAction(self.action.value)
        return IntentAction.HOLD


def parse_intent(raw_output: str) -> Result[BoundedIntent]:
    try:
        payload = json.loads(raw_output)
    except (TypeError, json.JSONDecodeError):
        return Result.hold("LLM_OUTPUT_INVALID_JSON")
    if not isinstance(payload, dict):
        return Result.hold("LLM_OUTPUT_NOT_OBJECT")
    if set(payload) - _ALLOWED_FIELDS:
        return Result.hold("LLM_OUTPUT_EXTRA_FIELDS")
    if _REQUIRED_FIELDS - set(payload):
        return Result.insufficient_data("LLM_OUTPUT_FIELDS_MISSING")
    if payload["risk_handoff_required"] is not True:
        return Result.hold("LLM_RISK_HANDOFF_REQUIRED")
    if not _string_list(payload["reason_codes"]) or not _string_list(payload["evidence_summary"]):
        return Result.hold("LLM_OUTPUT_LIST_FIELDS_INVALID")

    try:
        action = BoundedIntentAction(str(payload["intent"]))
        confidence = SignalConfidence(str(payload["confidence"]).lower())
        requested_notional = _requested_notional(payload, action)
    except (ValueError, InvalidOperation, TypeError):
        return Result.hold("LLM_OUTPUT_FIELDS_INVALID")
    return Result.success(
        BoundedIntent(
            action=action,
            confidence=confidence,
            reason_codes=tuple(payload["reason_codes"]),
            evidence_summary=tuple(payload["evidence_summary"]),
            requested_notional_usd=requested_notional,
        )
    )


def hold_intent(reason_code: str) -> BoundedIntent:
    return BoundedIntent(
        action=BoundedIntentAction.HOLD,
        confidence=SignalConfidence.UNKNOWN,
        reason_codes=(reason_code,),
        evidence_summary=("non-actionable bounded intent",),
    )


def _requested_notional(payload: dict[str, Any], action: BoundedIntentAction) -> Decimal:
    if action in (BoundedIntentAction.BUY, BoundedIntentAction.SELL):
        value = Decimal(str(payload.get("requested_notional_usd", "10")))
        if value <= Decimal("0"):
            raise ValueError("action notional must be positive")
        return value
    return Decimal("0")


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )

