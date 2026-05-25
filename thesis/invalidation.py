"""Deterministic invalidation rules for research thesis notes."""

from __future__ import annotations

from thesis.models import ThesisInputs


def build_invalidation_conditions(inputs: ThesisInputs) -> tuple[str, ...]:
    """Return mandatory conditions that would invalidate a research thesis."""

    conditions = [
        "Critical market data becomes stale, missing, malformed, or contradictory.",
        "Anti-rug evidence changes to unknown, incomplete, or hard-fail status.",
    ]
    if _number(inputs.liquidity_score) < 40:
        conditions.append("Liquidity remains thin or deteriorates further.")
    else:
        conditions.append("Liquidity drops below the local minimum needed for reliable research.")
    if _number(inputs.risk_score) >= 60:
        conditions.append("Risk score stays elevated or increases again.")
    else:
        conditions.append("Risk score rises into elevated territory.")
    if _number(inputs.opportunity_score) > 0:
        conditions.append("Opportunity score loses momentum versus the prior radar review.")
    return tuple(dict.fromkeys(conditions))


def build_exit_warning_conditions(inputs: ThesisInputs) -> tuple[str, ...]:
    """Return research-only exit warning conditions."""

    warnings = [
        "Radar state moves to AVOID, STALE, REVIEW, or EXIT_RISK.",
        "Liquidity drains materially versus the previous observation.",
        "Safety, holder, wallet, or contract evidence becomes incomplete.",
    ]
    if _number(inputs.risk_adjusted_score) < 30:
        warnings.append("Risk-adjusted score remains weak despite any opportunity signals.")
    if _number(inputs.risk_score) >= 75:
        warnings.append("Risk score is already high enough to require extra review.")
    return tuple(dict.fromkeys(warnings))


def _number(value: float | None) -> float:
    return 0.0 if value is None else float(value)
