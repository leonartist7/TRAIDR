"""In-memory simulation portfolio state updated by paper fills only."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from execution.models import SimulationFill
from risk.models import IntentAction

SIMULATION_STARTING_CASH_USD = Decimal("50")


@dataclass(frozen=True)
class SimulatedPosition:
    """Aggregate quantity and cost for one paper pair."""

    pair_id: str
    quantity: Decimal
    cost_usd: Decimal


@dataclass
class PortfolioStateLedger:
    """Small paper ledger; it has no exchange or custody boundary."""

    cash_usd: Decimal = SIMULATION_STARTING_CASH_USD
    positions: dict[str, SimulatedPosition] = field(default_factory=dict)

    @property
    def exposure_usd(self) -> Decimal:
        return sum((position.cost_usd for position in self.positions.values()), Decimal("0"))

    def apply_fill(
        self,
        *,
        pair_id: str,
        side: IntentAction,
        fill: SimulationFill,
    ) -> None:
        reasons = self.validate_fill(pair_id=pair_id, side=side, fill=fill)
        if reasons:
            raise ValueError(",".join(reasons))
        if side is IntentAction.BUY:
            self._apply_buy(pair_id, fill)
            return
        if side is IntentAction.SELL:
            self._apply_sell(pair_id, fill)
            return
        raise ValueError("paper ledger only applies buy and sell fills")

    def validate_fill(
        self,
        *,
        pair_id: str,
        side: IntentAction,
        fill: SimulationFill,
    ) -> tuple[str, ...]:
        if side is IntentAction.BUY and fill.notional_usd > self.cash_usd:
            return ("SIMULATED_CASH_INSUFFICIENT",)
        if side is IntentAction.SELL:
            current = self.positions.get(pair_id)
            if current is None or fill.quantity > current.quantity:
                return ("SIMULATED_HOLDINGS_INSUFFICIENT",)
        if side not in (IntentAction.BUY, IntentAction.SELL):
            return ("EXECUTABLE_SIDE_REQUIRED",)
        return ()

    def _apply_buy(self, pair_id: str, fill: SimulationFill) -> None:
        current = self.positions.get(pair_id)
        quantity = fill.quantity + (current.quantity if current else Decimal("0"))
        cost = fill.notional_usd + (current.cost_usd if current else Decimal("0"))
        self.cash_usd -= fill.notional_usd
        self.positions[pair_id] = SimulatedPosition(pair_id, quantity, cost)

    def _apply_sell(self, pair_id: str, fill: SimulationFill) -> None:
        current = self.positions.get(pair_id)
        if current is None:
            raise ValueError("validated simulated sell lost holdings")

        sold_fraction = fill.quantity / current.quantity
        remaining_quantity = current.quantity - fill.quantity
        remaining_cost = current.cost_usd * (Decimal("1") - sold_fraction)
        self.cash_usd += fill.notional_usd
        if remaining_quantity == Decimal("0"):
            del self.positions[pair_id]
        else:
            self.positions[pair_id] = SimulatedPosition(
                pair_id,
                remaining_quantity,
                remaining_cost,
            )
