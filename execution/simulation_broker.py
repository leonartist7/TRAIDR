"""Risk-gated paper broker for simulation-only fills."""

from __future__ import annotations

from decimal import Decimal

from execution.audit import ExecutionAudit
from execution.models import (
    ExecutionResult,
    ExecutionStatus,
    SimulationFill,
    SimulationOrder,
    SimulationOrderRequest,
)
from execution.order_validator import SimulationOrderValidator
from execution.portfolio_state import PortfolioStateLedger
from execution.slippage import DEFAULT_SLIPPAGE_RATE, quote_fill
from storage.repositories import SimulationRepository


class SimulationBroker:
    """Persist simulated orders and fills only after risk approval."""

    def __init__(
        self,
        *,
        repository: SimulationRepository,
        audit: ExecutionAudit,
        validator: SimulationOrderValidator | None = None,
        portfolio: PortfolioStateLedger | None = None,
        slippage_rate: Decimal = DEFAULT_SLIPPAGE_RATE,
    ) -> None:
        self.repository = repository
        self.audit = audit
        self.validator = validator or SimulationOrderValidator()
        self.portfolio = portfolio or PortfolioStateLedger()
        self.slippage_rate = slippage_rate

    def submit(self, request: SimulationOrderRequest) -> ExecutionResult:
        attempt_event = self.audit.record(
            event_type="simulation_execution_attempt",
            reason_codes=("SIMULATION_ATTEMPT_RECORDED",),
            request=request,
            recorded_at=request.created_at,
        )
        validation = self.validator.validate(request)
        if not validation.approved:
            status = (
                ExecutionStatus.INSUFFICIENT_DATA
                if validation.reason_codes == ("RISK_INSUFFICIENT_DATA",)
                else ExecutionStatus.HOLD
            )
            rejection_event = self.audit.record(
                event_type="simulation_execution_blocked",
                reason_codes=validation.reason_codes,
                request=request,
                severity="WARNING",
                recorded_at=request.created_at,
            )
            return ExecutionResult(
                status=status,
                reason_codes=validation.reason_codes,
                audit_event_ids=(attempt_event, rejection_event),
            )

        approved_notional = validation.approved_notional_usd
        if approved_notional is None:
            raise RuntimeError("approved simulation validation lost notional")

        quote = quote_fill(
            side=request.side,
            reference_price_usd=request.reference_price_usd,
            approved_notional_usd=approved_notional,
            fill_fraction=request.fill_fraction,
            slippage_rate=self.slippage_rate,
        )
        preview_fill = SimulationFill(
            fill_id="paper_preview",
            order_id="paper_preview",
            quantity=quote.quantity,
            price_usd=quote.price_usd,
            notional_usd=quote.notional_usd,
            fill_fraction=quote.fill_fraction,
        )
        portfolio_reasons = self.portfolio.validate_fill(
            pair_id=request.pair_id,
            side=request.side,
            fill=preview_fill,
        )
        if portfolio_reasons:
            portfolio_event = self.audit.record(
                event_type="simulation_execution_blocked",
                reason_codes=portfolio_reasons,
                request=request,
                severity="WARNING",
                recorded_at=request.created_at,
            )
            return ExecutionResult(
                status=ExecutionStatus.HOLD,
                reason_codes=portfolio_reasons,
                audit_event_ids=(attempt_event, portfolio_event),
            )

        order_status = "paper_partial" if quote.fill_fraction < Decimal("1") else "paper_filled"
        order_id = self.repository.record_order(
            risk_decision_id=request.risk_decision_id,
            side=request.side.value,
            pair_id=request.pair_id,
            notional_usd=approved_notional,
            order_status=order_status,
            metadata={
                "mode": "simulation",
                "reference_price_usd": str(request.reference_price_usd),
                **request.metadata,
            },
            created_at=request.created_at,
        )
        fill_id = self.repository.record_fill(
            order_id=order_id,
            quantity=quote.quantity,
            price_usd=quote.price_usd,
            notional_usd=quote.notional_usd,
            metadata={
                "mode": "simulation",
                "fill_fraction": str(quote.fill_fraction),
                "slippage_rate": str(self.slippage_rate),
            },
            filled_at=request.created_at,
        )
        order = SimulationOrder(
            order_id=order_id,
            risk_decision_id=request.risk_decision_id,
            pair_id=request.pair_id,
            side=request.side,
            requested_notional_usd=approved_notional,
            status=order_status,
        )
        fill = SimulationFill(
            fill_id=fill_id,
            order_id=order_id,
            quantity=quote.quantity,
            price_usd=quote.price_usd,
            notional_usd=quote.notional_usd,
            fill_fraction=quote.fill_fraction,
        )
        self.portfolio.apply_fill(pair_id=request.pair_id, side=request.side, fill=fill)
        fill_event = self.audit.record(
            event_type="simulation_execution_fill",
            reason_codes=("SIMULATION_FILL_RECORDED",),
            request=request,
            payload={
                "fill_id": fill_id,
                "order_id": order_id,
                "paper_notional_usd": str(fill.notional_usd),
            },
            recorded_at=request.created_at,
        )
        return ExecutionResult(
            status=(
                ExecutionStatus.PARTIALLY_FILLED
                if quote.fill_fraction < Decimal("1")
                else ExecutionStatus.FILLED
            ),
            reason_codes=("SIMULATION_FILL_RECORDED",),
            order=order,
            fill=fill,
            audit_event_ids=(attempt_event, fill_event),
        )
