"""Simulation-only deterministic portfolio limits."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from risk.models import IntentAction, PortfolioState

SIMULATION_BANKROLL_USD = Decimal("50")
MAX_POSITION_NOTIONAL_USD = Decimal("10")
MAX_TOTAL_EXPOSURE_USD = Decimal("30")
MAX_OPEN_POSITIONS = 3
DAILY_LOSS_HALT_USD = Decimal("5")


@dataclass(frozen=True)
class LimitAssessment:
    """Hold reasons found by deterministic portfolio limit checks."""

    hold_reasons: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return bool(self.hold_reasons)


def assess_limits(
    *,
    action: IntentAction,
    requested_notional_usd: Decimal,
    portfolio: PortfolioState,
) -> LimitAssessment:
    """Evaluate simulation bankroll and exposure limits fail closed."""

    hold_reasons: list[str] = []

    if portfolio.bankroll_usd != SIMULATION_BANKROLL_USD:
        hold_reasons.append("SIMULATION_BANKROLL_INVALID")
    if portfolio.current_exposure_usd < Decimal("0"):
        hold_reasons.append("EXPOSURE_INVALID")
    if portfolio.open_positions < 0:
        hold_reasons.append("OPEN_POSITION_COUNT_INVALID")
    if portfolio.daily_loss_usd < Decimal("0"):
        hold_reasons.append("DAILY_LOSS_INVALID")
    if portfolio.daily_loss_usd >= DAILY_LOSS_HALT_USD:
        hold_reasons.append("DAILY_LOSS_HALT")
    if requested_notional_usd < Decimal("0"):
        hold_reasons.append("REQUEST_NOTIONAL_INVALID")

    if action is IntentAction.BUY:
        if requested_notional_usd <= Decimal("0"):
            hold_reasons.append("BUY_NOTIONAL_REQUIRED")
        if requested_notional_usd > MAX_POSITION_NOTIONAL_USD:
            hold_reasons.append("MAX_POSITION_NOTIONAL_EXCEEDED")
        if portfolio.open_positions >= MAX_OPEN_POSITIONS:
            hold_reasons.append("MAX_OPEN_POSITIONS_REACHED")
        if portfolio.current_exposure_usd + requested_notional_usd > MAX_TOTAL_EXPOSURE_USD:
            hold_reasons.append("MAX_TOTAL_EXPOSURE_EXCEEDED")
    elif action is IntentAction.SELL and requested_notional_usd <= Decimal("0"):
        hold_reasons.append("SELL_NOTIONAL_REQUIRED")

    return LimitAssessment(tuple(dict.fromkeys(hold_reasons)))

