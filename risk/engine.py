"""Deterministic simulation-first risk engine."""

from __future__ import annotations

from datetime import timedelta

from risk.anti_rug import assess_anti_rug
from risk.limits import assess_limits
from risk.models import (
    IntentAction,
    RiskDecision,
    RiskOutcome,
    RiskRequest,
    SignalConfidence,
)
from utils.clocks import check_freshness

DEFAULT_MAX_DATA_AGE = timedelta(minutes=5)


class RiskEngine:
    """Validate bounded intents before any later paper execution path."""

    def __init__(self, *, max_data_age: timedelta = DEFAULT_MAX_DATA_AGE) -> None:
        self.max_data_age = max_data_age

    def evaluate(self, request: RiskRequest) -> RiskDecision:
        """Evaluate an intent with hard safety vetoes before limit approval."""

        anti_rug = assess_anti_rug(request.anti_rug)
        if anti_rug.hard_failed:
            return _hold(request.action, *anti_rug.hard_fail_reasons)
        if anti_rug.insufficient_data:
            return _insufficient(request.action, *anti_rug.insufficient_data_reasons)

        data_quality_reasons = _data_quality_reasons(request)
        if data_quality_reasons:
            return _insufficient(request.action, *data_quality_reasons)

        freshness = check_freshness(
            request.market_data.observed_at,
            max_age=self.max_data_age,
            now=request.now,
        )
        if not freshness.ok:
            return _insufficient(request.action, *freshness.reason_codes)

        if request.mode != "simulation":
            return _hold(request.action, "MODE_NOT_SIMULATION")
        if request.action is IntentAction.HOLD:
            return _hold(request.action, "INTENT_DEFAULT_HOLD")
        if request.confidence in (SignalConfidence.LOW, SignalConfidence.UNKNOWN):
            return _hold(request.action, "CONFIDENCE_TOO_LOW")

        limits = assess_limits(
            action=request.action,
            requested_notional_usd=request.requested_notional_usd,
            portfolio=request.portfolio,
        )
        if limits.blocked:
            return _hold(request.action, *limits.hold_reasons)

        return RiskDecision(
            outcome=RiskOutcome.APPROVED,
            action=request.action,
            reason_codes=("RISK_APPROVED_SIMULATION_ONLY",),
            approved_notional_usd=request.requested_notional_usd,
        )


def _data_quality_reasons(request: RiskRequest) -> tuple[str, ...]:
    market_data = request.market_data
    reasons: list[str] = []
    if not market_data.provenance_known:
        reasons.append("DATA_PROVENANCE_MISSING")
    if market_data.malformed:
        reasons.append("DATA_MALFORMED")
    if market_data.contradictory:
        reasons.append("DATA_CONTRADICTORY")
    if market_data.uncertain:
        reasons.append("DATA_UNCERTAIN")
    return tuple(reasons)


def _hold(action: IntentAction, *reason_codes: str) -> RiskDecision:
    return RiskDecision(
        outcome=RiskOutcome.HOLD,
        action=action,
        reason_codes=tuple(reason_codes),
    )


def _insufficient(action: IntentAction, *reason_codes: str) -> RiskDecision:
    return RiskDecision(
        outcome=RiskOutcome.INSUFFICIENT_DATA,
        action=action,
        reason_codes=tuple(reason_codes),
    )

