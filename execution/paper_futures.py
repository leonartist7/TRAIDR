"""Deterministic perpetual-futures paper simulator; no exchange route exists."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal, ROUND_DOWN
from enum import Enum
from hashlib import sha256
from typing import Any, Mapping

from intelligence.production_models import SignalDecision, SignalDirection
from utils.results import Result


class PaperPositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"


@dataclass(frozen=True)
class PaperFuturesLimits:
    starting_equity_usd: Decimal = Decimal("50")
    default_leverage: Decimal = Decimal("1")
    maximum_leverage: Decimal = Decimal("2")
    risk_per_position_fraction: Decimal = Decimal("0.005")
    maximum_positions: int = 3
    maximum_margin_fraction: Decimal = Decimal("0.30")
    daily_drawdown_halt_fraction: Decimal = Decimal("0.03")
    maintenance_margin_fraction: Decimal = Decimal("0.005")
    taker_fee_bps: Decimal = Decimal("6")
    default_slippage_bps: Decimal = Decimal("3")
    latency_slippage_bps_per_second: Decimal = Decimal("1")
    liquidation_penalty_bps: Decimal = Decimal("25")
    accounting_tolerance_usd: Decimal = Decimal("0.000001")


@dataclass(frozen=True)
class PaperFuturesOrder:
    order_id: str
    signal_id: str
    instrument_id: str
    direction: SignalDirection
    created_at: datetime
    leverage: Decimal
    requested_notional_usd: Decimal
    requested_margin_usd: Decimal
    reference_price: Decimal
    status: str
    idempotency_key: str
    can_execute_trades: bool = False


@dataclass(frozen=True)
class PaperFuturesFill:
    fill_id: str
    order_id: str
    filled_at: datetime
    quantity: Decimal
    fill_price: Decimal
    notional_usd: Decimal
    fee_usd: Decimal
    slippage_bps: Decimal
    can_execute_trades: bool = False


@dataclass(frozen=True)
class PaperPosition:
    position_id: str
    instrument_id: str
    direction: SignalDirection
    opened_at: datetime
    updated_at: datetime
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    leverage: Decimal
    initial_margin_usd: Decimal
    maintenance_margin_usd: Decimal
    liquidation_price: Decimal
    stop_price: Decimal
    targets: tuple[Decimal, ...]
    expires_at: datetime | None = None
    trailing_stop_price: Decimal | None = None
    trailing_distance_fraction: Decimal | None = None
    realized_pnl_usd: Decimal = Decimal("0")
    unrealized_pnl_usd: Decimal = Decimal("0")
    fees_paid_usd: Decimal = Decimal("0")
    funding_paid_usd: Decimal = Decimal("0")
    status: PaperPositionStatus = PaperPositionStatus.OPEN
    can_execute_trades: bool = False


@dataclass(frozen=True)
class PaperPortfolioSnapshot:
    captured_at: datetime
    starting_equity_usd: Decimal
    cash_usd: Decimal
    equity_usd: Decimal
    used_margin_usd: Decimal
    unrealized_pnl_usd: Decimal
    realized_pnl_usd: Decimal
    daily_pnl_usd: Decimal
    open_positions: tuple[PaperPosition, ...]
    halted: bool
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False


@dataclass
class PaperFuturesSimulator:
    """In-memory accounting engine designed to be restored from DuckDB records."""

    limits: PaperFuturesLimits = field(default_factory=PaperFuturesLimits)
    cash_usd: Decimal | None = None
    realized_pnl_usd: Decimal = Decimal("0")
    daily_pnl_usd: Decimal = Decimal("0")
    positions: dict[str, PaperPosition] = field(default_factory=dict)
    processed_idempotency_keys: set[str] = field(default_factory=set)
    processed_funding_keys: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.cash_usd is None:
            self.cash_usd = self.limits.starting_equity_usd

    @classmethod
    def from_persisted_portfolio(
        cls,
        payload: Mapping[str, Any] | None,
        *,
        limits: PaperFuturesLimits | None = None,
        processed_idempotency_keys: tuple[str, ...] = (),
    ) -> "PaperFuturesSimulator":
        """Restore the last durable paper state; malformed state fails closed to empty."""

        selected_limits = limits or PaperFuturesLimits()
        if not payload:
            return cls(
                limits=selected_limits,
                processed_idempotency_keys=set(processed_idempotency_keys),
            )
        try:
            positions = {
                str(item["instrument_id"]): _position_from_mapping(item)
                for item in payload.get("open_positions", ())
                if isinstance(item, Mapping)
            }
            return cls(
                limits=selected_limits,
                cash_usd=Decimal(str(payload["cash_usd"])),
                realized_pnl_usd=Decimal(str(payload["realized_pnl_usd"])),
                daily_pnl_usd=Decimal(str(payload["daily_pnl_usd"])),
                positions=positions,
                processed_idempotency_keys=set(processed_idempotency_keys),
                processed_funding_keys=set(str(value) for value in payload.get("processed_funding_keys", ())),
            )
        except (KeyError, TypeError, ValueError):
            return cls(
                limits=selected_limits,
                cash_usd=Decimal("0"),
                daily_pnl_usd=-selected_limits.starting_equity_usd,
                processed_idempotency_keys=set(processed_idempotency_keys),
                processed_funding_keys=set(),
            )

    def open_from_signal(
        self,
        signal: SignalDecision,
        *,
        mark_price: Decimal,
        risk_approved: bool,
        market_data_fresh: bool,
        depth_available: bool,
        leverage: Decimal | None = None,
        manual_or_auto_paper_enabled: bool = False,
        available_depth_notional_usd: Decimal | None = None,
        latency_ms: int = 0,
        now: datetime | None = None,
    ) -> Result[tuple[PaperFuturesOrder, PaperFuturesFill, PaperPosition]]:
        reference = now or datetime.now(tz=UTC)
        if not manual_or_auto_paper_enabled:
            return Result.hold("PAPER_SIMULATION_NOT_ENABLED")
        if not risk_approved:
            return Result.hold("DETERMINISTIC_RISK_NOT_APPROVED")
        if signal.direction is SignalDirection.NO_TRADE or signal.hard_vetoes:
            return Result.hold("SIGNAL_NOT_ACTIONABLE")
        if not market_data_fresh or not depth_available:
            return Result.insufficient_data("PAPER_MARKET_DATA_INSUFFICIENT")
        if signal.expires_at <= reference:
            return Result.insufficient_data("SIGNAL_EXPIRED")
        if signal.stop is None or not signal.targets or mark_price <= 0:
            return Result.insufficient_data("PAPER_BRACKET_OR_PRICE_MISSING")
        if signal.idempotency_key in self.processed_idempotency_keys:
            return Result.hold("PAPER_DUPLICATE_SIGNAL")
        if signal.instrument_id in self.positions and self.positions[signal.instrument_id].status is PaperPositionStatus.OPEN:
            return Result.hold("PAPER_AVERAGING_DOWN_FORBIDDEN")
        if len(self.open_positions()) >= self.limits.maximum_positions:
            return Result.hold("PAPER_MAX_POSITIONS_REACHED")
        portfolio = self.snapshot(reference)
        if portfolio.halted:
            return Result.hold(*portfolio.reason_codes)

        selected_leverage = leverage or self.limits.default_leverage
        if selected_leverage < 1 or selected_leverage > self.limits.maximum_leverage:
            return Result.hold("PAPER_LEVERAGE_LIMIT")
        stop_fraction = abs(mark_price - signal.stop) / mark_price
        if stop_fraction <= 0:
            return Result.insufficient_data("PAPER_STOP_DISTANCE_INVALID")
        risk_budget = portfolio.equity_usd * self.limits.risk_per_position_fraction
        notional = risk_budget / stop_fraction
        margin_cap = portfolio.equity_usd * self.limits.maximum_margin_fraction - portfolio.used_margin_usd
        notional = min(notional, max(Decimal("0"), margin_cap) * selected_leverage)
        requested_notional = notional.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        if requested_notional <= 0:
            return Result.hold("PAPER_MARGIN_CAP_REACHED")
        if available_depth_notional_usd is not None and available_depth_notional_usd <= 0:
            return Result.insufficient_data("PAPER_AVAILABLE_DEPTH_ZERO")
        notional = min(requested_notional, available_depth_notional_usd or requested_notional)
        notional = notional.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        margin = notional / selected_leverage
        latency_bps = Decimal(max(0, latency_ms)) / Decimal("1000") * self.limits.latency_slippage_bps_per_second
        slippage_bps = self.limits.default_slippage_bps + latency_bps
        slippage = slippage_bps / Decimal("10000")
        fill_price = mark_price * (Decimal("1") + slippage if signal.direction is SignalDirection.LONG else Decimal("1") - slippage)
        quantity = notional / fill_price
        fee = notional * self.limits.taker_fee_bps / Decimal("10000")
        if self.cash_usd is None or self.cash_usd < margin + fee:
            return Result.hold("PAPER_CASH_INSUFFICIENT")

        digest = sha256(f"{signal.signal_id}|{reference.isoformat()}|paper-futures-v1".encode("utf-8")).hexdigest()[:24]
        order = PaperFuturesOrder(
            order_id=f"pf-order-{digest}",
            signal_id=signal.signal_id,
            instrument_id=signal.instrument_id,
            direction=signal.direction,
            created_at=reference,
            leverage=selected_leverage,
            requested_notional_usd=requested_notional,
            requested_margin_usd=requested_notional / selected_leverage,
            reference_price=mark_price,
            status="FILLED" if notional == requested_notional else "PARTIAL",
            idempotency_key=signal.idempotency_key,
        )
        fill = PaperFuturesFill(
            fill_id=f"pf-fill-{digest}",
            order_id=order.order_id,
            filled_at=reference,
            quantity=quantity,
            fill_price=fill_price,
            notional_usd=notional,
            fee_usd=fee,
            slippage_bps=slippage_bps,
        )
        liquidation = self._liquidation_price(fill_price, selected_leverage, signal.direction)
        position = PaperPosition(
            position_id=f"pf-position-{digest}",
            instrument_id=signal.instrument_id,
            direction=signal.direction,
            opened_at=reference,
            updated_at=reference,
            quantity=quantity,
            entry_price=fill_price,
            mark_price=mark_price,
            leverage=selected_leverage,
            initial_margin_usd=margin,
            maintenance_margin_usd=notional * self.limits.maintenance_margin_fraction,
            liquidation_price=liquidation,
            stop_price=signal.stop,
            targets=signal.targets,
            expires_at=signal.expires_at,
            fees_paid_usd=fee,
        )
        self.cash_usd -= margin + fee
        self.realized_pnl_usd -= fee
        self.daily_pnl_usd -= fee
        self.positions[signal.instrument_id] = position
        self.processed_idempotency_keys.add(signal.idempotency_key)
        self._assert_reconciled()
        return Result.success((order, fill, position))

    def mark(self, instrument_id: str, mark_price: Decimal, *, now: datetime | None = None) -> Result[PaperPosition]:
        position = self.positions.get(instrument_id)
        if position is None or position.status is not PaperPositionStatus.OPEN:
            return Result.insufficient_data("PAPER_POSITION_NOT_OPEN")
        if mark_price <= 0:
            return Result.insufficient_data("PAPER_MARK_PRICE_INVALID")
        reference = now or datetime.now(tz=UTC)
        pnl = self._position_pnl(position, mark_price, position.quantity)
        status = PaperPositionStatus.OPEN
        if (position.direction is SignalDirection.LONG and mark_price <= position.liquidation_price) or (
            position.direction is SignalDirection.SHORT and mark_price >= position.liquidation_price
        ):
            status = PaperPositionStatus.LIQUIDATED
        if status is PaperPositionStatus.LIQUIDATED:
            return self.close(instrument_id, exit_price=mark_price, fraction=Decimal("1"), now=reference, liquidated=True)
        updated = replace(position, mark_price=mark_price, unrealized_pnl_usd=pnl, updated_at=reference, status=status)
        self.positions[instrument_id] = updated
        self._assert_reconciled()
        return Result.success(updated)

    def process_price(
        self,
        instrument_id: str,
        mark_price: Decimal,
        *,
        now: datetime | None = None,
    ) -> Result[PaperPosition]:
        """Apply liquidation, adverse gap-stop, or the next target conservatively."""

        position = self.positions.get(instrument_id)
        if position is None or position.status is not PaperPositionStatus.OPEN:
            return Result.insufficient_data("PAPER_POSITION_NOT_OPEN")
        reference = now or datetime.now(tz=UTC)
        if position.expires_at is not None and reference >= position.expires_at:
            return self.close(instrument_id, exit_price=mark_price, fraction=Decimal("1"), now=reference)
        liquidation_crossed = (
            position.direction is SignalDirection.LONG and mark_price <= position.liquidation_price
        ) or (
            position.direction is SignalDirection.SHORT and mark_price >= position.liquidation_price
        )
        if liquidation_crossed:
            return self.close(
                instrument_id,
                exit_price=mark_price,
                fraction=Decimal("1"),
                now=reference,
                liquidated=True,
            )
        effective_stop = position.trailing_stop_price or position.stop_price
        stop_crossed = (
            position.direction is SignalDirection.LONG and mark_price <= effective_stop
        ) or (
            position.direction is SignalDirection.SHORT and mark_price >= effective_stop
        )
        if stop_crossed:
            return self.close(
                instrument_id,
                exit_price=mark_price,
                fraction=Decimal("1"),
                now=reference,
            )
        if position.targets:
            target = position.targets[0]
            target_crossed = (
                position.direction is SignalDirection.LONG and mark_price >= target
            ) or (
                position.direction is SignalDirection.SHORT and mark_price <= target
            )
            if target_crossed:
                fraction = Decimal("1") if len(position.targets) == 1 else Decimal("0.5")
                result = self.close(
                    instrument_id,
                    exit_price=mark_price,
                    fraction=fraction,
                    now=reference,
                )
                if result.ok and result.value is not None:
                    updated = replace(result.value, targets=position.targets[1:])
                    self.positions[instrument_id] = updated
                    return Result.success(updated)
                return result
        if position.trailing_distance_fraction is not None:
            distance = mark_price * position.trailing_distance_fraction
            proposed = mark_price - distance if position.direction is SignalDirection.LONG else mark_price + distance
            current = position.trailing_stop_price or position.stop_price
            trailing = max(current, proposed) if position.direction is SignalDirection.LONG else min(current, proposed)
            position = replace(position, trailing_stop_price=trailing, updated_at=reference)
            self.positions[instrument_id] = position
        return self.mark(instrument_id, mark_price, now=reference)

    def apply_funding(
        self,
        instrument_id: str,
        funding_rate: Decimal,
        *,
        funding_time: datetime | None = None,
    ) -> Result[PaperPosition]:
        position = self.positions.get(instrument_id)
        if position is None or position.status is not PaperPositionStatus.OPEN:
            return Result.insufficient_data("PAPER_POSITION_NOT_OPEN")
        scheduled = funding_time or datetime.now(tz=UTC)
        if scheduled < position.opened_at:
            return Result.hold("PAPER_FUNDING_PREDATES_POSITION")
        funding_key = f"{position.position_id}|{scheduled.astimezone(UTC).isoformat()}"
        if funding_key in self.processed_funding_keys:
            return Result.hold("PAPER_FUNDING_ALREADY_APPLIED")
        direction_multiplier = Decimal("1") if position.direction is SignalDirection.LONG else Decimal("-1")
        payment = position.quantity * position.mark_price * funding_rate * direction_multiplier
        if self.cash_usd is None:
            return Result.insufficient_data("PAPER_CASH_STATE_MISSING")
        self.cash_usd -= payment
        self.realized_pnl_usd -= payment
        self.daily_pnl_usd -= payment
        updated = replace(position, funding_paid_usd=position.funding_paid_usd + payment)
        self.positions[instrument_id] = updated
        self.processed_funding_keys.add(funding_key)
        self._assert_reconciled()
        return Result.success(updated)

    def enable_trailing_stop(
        self,
        instrument_id: str,
        *,
        distance_fraction: Decimal,
    ) -> Result[PaperPosition]:
        position = self.positions.get(instrument_id)
        if position is None or position.status is not PaperPositionStatus.OPEN:
            return Result.insufficient_data("PAPER_POSITION_NOT_OPEN")
        if distance_fraction <= 0 or distance_fraction >= Decimal("0.25"):
            return Result.insufficient_data("PAPER_TRAILING_DISTANCE_INVALID")
        distance = position.mark_price * distance_fraction
        proposed = (
            position.mark_price - distance
            if position.direction is SignalDirection.LONG
            else position.mark_price + distance
        )
        stop = max(position.stop_price, proposed) if position.direction is SignalDirection.LONG else min(position.stop_price, proposed)
        updated = replace(
            position,
            trailing_stop_price=stop,
            trailing_distance_fraction=distance_fraction,
        )
        self.positions[instrument_id] = updated
        return Result.success(updated)

    def close(
        self,
        instrument_id: str,
        *,
        exit_price: Decimal,
        fraction: Decimal = Decimal("1"),
        now: datetime | None = None,
        liquidated: bool = False,
    ) -> Result[PaperPosition]:
        position = self.positions.get(instrument_id)
        if position is None or position.status is not PaperPositionStatus.OPEN:
            return Result.insufficient_data("PAPER_POSITION_NOT_OPEN")
        if exit_price <= 0 or fraction <= 0 or fraction > 1:
            return Result.insufficient_data("PAPER_CLOSE_REQUEST_INVALID")
        reference = now or datetime.now(tz=UTC)
        close_quantity = position.quantity * fraction
        pnl = self._position_pnl(position, exit_price, close_quantity)
        notional = close_quantity * exit_price
        fee_bps = self.limits.taker_fee_bps + (self.limits.liquidation_penalty_bps if liquidated else Decimal("0"))
        fee = notional * fee_bps / Decimal("10000")
        released_margin = position.initial_margin_usd * fraction
        realized = pnl - fee
        if self.cash_usd is None:
            return Result.insufficient_data("PAPER_CASH_STATE_MISSING")
        self.cash_usd += released_margin + realized
        self.realized_pnl_usd += realized
        self.daily_pnl_usd += realized
        remaining = position.quantity - close_quantity
        status = PaperPositionStatus.LIQUIDATED if liquidated else PaperPositionStatus.CLOSED if remaining == 0 else PaperPositionStatus.OPEN
        updated = replace(
            position,
            updated_at=reference,
            quantity=remaining,
            mark_price=exit_price,
            initial_margin_usd=position.initial_margin_usd - released_margin,
            realized_pnl_usd=position.realized_pnl_usd + realized,
            unrealized_pnl_usd=Decimal("0") if remaining == 0 else self._position_pnl(position, exit_price, remaining),
            fees_paid_usd=position.fees_paid_usd + fee,
            status=status,
        )
        self.positions[instrument_id] = updated
        self._assert_reconciled()
        return Result.success(updated)

    def open_positions(self) -> tuple[PaperPosition, ...]:
        return tuple(position for position in self.positions.values() if position.status is PaperPositionStatus.OPEN)

    def snapshot(self, now: datetime | None = None) -> PaperPortfolioSnapshot:
        reference = now or datetime.now(tz=UTC)
        open_positions = self.open_positions()
        used_margin = sum((position.initial_margin_usd for position in open_positions), Decimal("0"))
        unrealized = sum((position.unrealized_pnl_usd for position in open_positions), Decimal("0"))
        cash = self.cash_usd or Decimal("0")
        equity = cash + used_margin + unrealized
        drawdown_limit = self.limits.starting_equity_usd * self.limits.daily_drawdown_halt_fraction
        halted = self.daily_pnl_usd <= -drawdown_limit
        reasons = ("PAPER_DAILY_DRAWDOWN_HALT",) if halted else ("PAPER_PORTFOLIO_ACTIVE",)
        return PaperPortfolioSnapshot(
            captured_at=reference,
            starting_equity_usd=self.limits.starting_equity_usd,
            cash_usd=cash,
            equity_usd=equity,
            used_margin_usd=used_margin,
            unrealized_pnl_usd=unrealized,
            realized_pnl_usd=self.realized_pnl_usd,
            daily_pnl_usd=self.daily_pnl_usd,
            open_positions=open_positions,
            halted=halted,
            reason_codes=reasons,
        )

    def reconcile(self) -> Decimal:
        snapshot = self.snapshot()
        expected = self.limits.starting_equity_usd + self.realized_pnl_usd + snapshot.unrealized_pnl_usd
        return snapshot.equity_usd - expected

    def _assert_reconciled(self) -> None:
        drift = abs(self.reconcile())
        if drift > self.limits.accounting_tolerance_usd:
            raise RuntimeError(f"paper accounting drift exceeded tolerance: {drift}")

    def _liquidation_price(self, entry: Decimal, leverage: Decimal, direction: SignalDirection) -> Decimal:
        maintenance = self.limits.maintenance_margin_fraction
        if direction is SignalDirection.LONG:
            return max(Decimal("0"), entry * (Decimal("1") - Decimal("1") / leverage + maintenance))
        return entry * (Decimal("1") + Decimal("1") / leverage - maintenance)

    @staticmethod
    def _position_pnl(position: PaperPosition, price: Decimal, quantity: Decimal) -> Decimal:
        multiplier = Decimal("1") if position.direction is SignalDirection.LONG else Decimal("-1")
        return (price - position.entry_price) * quantity * multiplier


def _position_from_mapping(item: Mapping[str, Any]) -> PaperPosition:
    return PaperPosition(
        position_id=str(item["position_id"]),
        instrument_id=str(item["instrument_id"]),
        direction=SignalDirection(str(item["direction"])),
        opened_at=datetime.fromisoformat(str(item["opened_at"])),
        updated_at=datetime.fromisoformat(str(item["updated_at"])),
        quantity=Decimal(str(item["quantity"])),
        entry_price=Decimal(str(item["entry_price"])),
        mark_price=Decimal(str(item["mark_price"])),
        leverage=Decimal(str(item["leverage"])),
        initial_margin_usd=Decimal(str(item["initial_margin_usd"])),
        maintenance_margin_usd=Decimal(str(item["maintenance_margin_usd"])),
        liquidation_price=Decimal(str(item["liquidation_price"])),
        stop_price=Decimal(str(item["stop_price"])),
        targets=tuple(Decimal(str(value)) for value in item.get("targets", ())),
        expires_at=datetime.fromisoformat(str(item["expires_at"])) if item.get("expires_at") else None,
        trailing_stop_price=Decimal(str(item["trailing_stop_price"])) if item.get("trailing_stop_price") else None,
        trailing_distance_fraction=Decimal(str(item["trailing_distance_fraction"])) if item.get("trailing_distance_fraction") else None,
        realized_pnl_usd=Decimal(str(item.get("realized_pnl_usd", "0"))),
        unrealized_pnl_usd=Decimal(str(item.get("unrealized_pnl_usd", "0"))),
        fees_paid_usd=Decimal(str(item.get("fees_paid_usd", "0"))),
        funding_paid_usd=Decimal(str(item.get("funding_paid_usd", "0"))),
        status=PaperPositionStatus(str(item.get("status", "OPEN"))),
    )
