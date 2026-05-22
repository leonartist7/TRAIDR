"""Simulation-only execution models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from risk.models import IntentAction, RiskDecision
from utils.toon import JsonValue


class ExecutionStatus(str, Enum):
    """Execution outcomes visible to later orchestration."""

    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    HOLD = "HOLD"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class SimulationOrderRequest:
    """Risk-approved candidate for a paper-only order."""

    risk_decision_id: str
    risk_decision: RiskDecision
    pair_id: str
    reference_price_usd: Decimal
    fill_fraction: Decimal = Decimal("1")
    mode: str = "simulation"
    created_at: datetime | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    @property
    def side(self) -> IntentAction:
        return self.risk_decision.action


@dataclass(frozen=True)
class SimulationOrder:
    """Persisted paper order record."""

    order_id: str
    risk_decision_id: str
    pair_id: str
    side: IntentAction
    requested_notional_usd: Decimal
    status: str


@dataclass(frozen=True)
class SimulationFill:
    """Paper fill record after slippage and partial-fill simulation."""

    fill_id: str
    order_id: str
    quantity: Decimal
    price_usd: Decimal
    notional_usd: Decimal
    fill_fraction: Decimal


@dataclass(frozen=True)
class ExecutionResult:
    """Broker result; HOLD and INSUFFICIENT_DATA never contain fills."""

    status: ExecutionStatus
    reason_codes: tuple[str, ...]
    order: SimulationOrder | None = None
    fill: SimulationFill | None = None
    audit_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "audit_event_ids", tuple(self.audit_event_ids))
        if not self.reason_codes:
            raise ValueError("execution results require reason codes")
        if self.status in (ExecutionStatus.HOLD, ExecutionStatus.INSUFFICIENT_DATA):
            if self.order is not None or self.fill is not None:
                raise ValueError("non-executed results cannot carry paper records")
        elif self.order is None or self.fill is None:
            raise ValueError("filled execution results require paper order and fill")

    @property
    def executed(self) -> bool:
        return self.status in (ExecutionStatus.FILLED, ExecutionStatus.PARTIALLY_FILLED)

