"""Deterministic risk engine models for simulation-only validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class IntentAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class RiskOutcome(str, Enum):
    APPROVED = "APPROVED"
    HOLD = "HOLD"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class AntiRugEvidence:
    """Required anti-rug safety observations for a risk request."""

    liquidity_accessible: bool | None
    liquidity_meets_floor: bool | None
    liquidity_status_known: bool | None
    mint_freeze_or_sell_restriction: bool | None
    unsafe_holder_or_creator_control: bool | None
    honeypot_tax_route_or_sellability_issue: bool | None
    identity_ambiguous: bool | None
    evidence_complete: bool | None


@dataclass(frozen=True)
class MarketDataState:
    """Freshness and provenance state for an intent's supporting data."""

    observed_at: datetime | str | None
    provenance_known: bool
    malformed: bool = False
    contradictory: bool = False
    uncertain: bool = False


@dataclass(frozen=True)
class PortfolioState:
    """Portfolio counters the risk engine needs before paper execution."""

    bankroll_usd: Decimal
    current_exposure_usd: Decimal
    open_positions: int
    daily_loss_usd: Decimal


@dataclass(frozen=True)
class RiskRequest:
    """Bounded input for deterministic risk evaluation."""

    action: IntentAction
    confidence: SignalConfidence
    requested_notional_usd: Decimal
    portfolio: PortfolioState
    market_data: MarketDataState
    anti_rug: AntiRugEvidence
    mode: str = "simulation"
    now: datetime | str | None = None


@dataclass(frozen=True)
class RiskDecision:
    """Deterministic output; only APPROVED may reach later paper execution."""

    outcome: RiskOutcome
    action: IntentAction
    reason_codes: tuple[str, ...]
    approved_notional_usd: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        if not self.reason_codes:
            raise ValueError("risk decisions require reason codes")
        if self.outcome is RiskOutcome.APPROVED and self.approved_notional_usd is None:
            raise ValueError("approved decisions require approved notional")
        if self.outcome is not RiskOutcome.APPROVED and self.approved_notional_usd is not None:
            raise ValueError("unsafe decisions cannot approve notional")

    @property
    def approved(self) -> bool:
        return self.outcome is RiskOutcome.APPROVED

