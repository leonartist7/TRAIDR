"""Final paper-order validation at the simulation execution boundary."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from execution.models import SimulationOrderRequest
from risk.models import IntentAction, RiskOutcome

_DEFAULT_RISK_CONFIG = Path(__file__).resolve().parents[1] / "config" / "risk.yaml"


@dataclass(frozen=True)
class OrderValidation:
    """Fail-closed order validation result."""

    approved: bool
    reason_codes: tuple[str, ...]
    approved_notional_usd: Decimal | None = None


class SimulationOrderValidator:
    """Require deterministic RiskEngine approval before paper orders."""

    def __init__(self, risk_config_path: str | Path = _DEFAULT_RISK_CONFIG) -> None:
        self.risk_config_path = Path(risk_config_path)

    def validate(self, request: SimulationOrderRequest) -> OrderValidation:
        reasons: list[str] = []

        if request.mode != "simulation":
            reasons.append("EXECUTION_MODE_NOT_SIMULATION")
        if request.risk_decision.outcome is RiskOutcome.INSUFFICIENT_DATA:
            return OrderValidation(False, ("RISK_INSUFFICIENT_DATA",))
        if request.risk_decision.outcome is not RiskOutcome.APPROVED:
            return OrderValidation(False, ("RISK_APPROVAL_REQUIRED",))
        if request.side not in (IntentAction.BUY, IntentAction.SELL):
            reasons.append("EXECUTABLE_SIDE_REQUIRED")
        if not request.risk_decision_id.strip():
            reasons.append("RISK_DECISION_ID_REQUIRED")
        if not request.pair_id.strip():
            reasons.append("PAIR_ID_REQUIRED")
        if request.reference_price_usd <= Decimal("0"):
            reasons.append("REFERENCE_PRICE_INVALID")
        if request.fill_fraction <= Decimal("0") or request.fill_fraction > Decimal("1"):
            reasons.append("FILL_FRACTION_INVALID")

        approved_notional = request.risk_decision.approved_notional_usd
        if approved_notional is None or approved_notional <= Decimal("0"):
            reasons.append("APPROVED_NOTIONAL_INVALID")

        max_notional = self._load_max_position_notional()
        if max_notional is None:
            reasons.append("RISK_CONFIG_UNAVAILABLE")
        elif approved_notional is not None and approved_notional > max_notional:
            reasons.append("CONFIG_MAX_POSITION_EXCEEDED")

        if reasons:
            return OrderValidation(False, tuple(dict.fromkeys(reasons)))
        return OrderValidation(
            True,
            ("SIMULATION_ORDER_VALIDATED",),
            approved_notional_usd=approved_notional,
        )

    def _load_max_position_notional(self) -> Decimal | None:
        try:
            with self.risk_config_path.open(encoding="utf-8") as config_file:
                config = yaml.safe_load(config_file)
            raw_value: Any = config["simulation_limits"]["max_position_notional_usd"]
            value = Decimal(str(raw_value))
        except (FileNotFoundError, KeyError, TypeError, InvalidOperation, yaml.YAMLError):
            return None

        return value if value > Decimal("0") else None

