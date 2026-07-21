"""Deterministic rolling-correlation, concentration, and simultaneous-loss stress."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from math import sqrt
from typing import Mapping, Sequence

from execution.paper_futures import PaperPortfolioSnapshot


@dataclass(frozen=True)
class PaperStressSnapshot:
    stress_id: str
    captured_at: datetime
    portfolio_equity_usd: Decimal
    stressed_loss_usd: Decimal
    maximum_correlation: float
    concentration_fraction: float
    approved: bool
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False


def assess_portfolio_stress(
    portfolio: PaperPortfolioSnapshot,
    returns_by_instrument: Mapping[str, Sequence[float]],
    *,
    stress_move_fraction: Decimal = Decimal("0.08"),
    maximum_correlation: float = 0.85,
    maximum_stressed_loss_fraction: Decimal = Decimal("0.03"),
) -> PaperStressSnapshot:
    positions = portfolio.open_positions
    notionals = {
        position.instrument_id: position.quantity * position.mark_price
        for position in positions
    }
    total_notional = sum(notionals.values(), Decimal("0"))
    concentration = (
        float(max(notionals.values()) / total_notional)
        if notionals and total_notional > 0
        else 0.0
    )
    correlations: list[float] = []
    instruments = sorted(notionals)
    for index, left in enumerate(instruments):
        for right in instruments[index + 1:]:
            correlation = _correlation(returns_by_instrument.get(left, ()), returns_by_instrument.get(right, ()))
            if correlation is not None:
                correlations.append(correlation)
    highest = max(correlations, default=0.0)
    stressed_loss = total_notional * stress_move_fraction * Decimal(str(max(1.0, highest)))
    loss_limit = portfolio.equity_usd * maximum_stressed_loss_fraction
    concentration_ok = len(notionals) <= 1 or concentration <= 0.60
    approved = highest <= maximum_correlation and stressed_loss <= loss_limit and concentration_ok
    reasons: list[str] = []
    if highest > maximum_correlation:
        reasons.append("PAPER_CORRELATION_LIMIT")
    if stressed_loss > loss_limit:
        reasons.append("PAPER_SIMULTANEOUS_LOSS_LIMIT")
    if not concentration_ok:
        reasons.append("PAPER_CONCENTRATION_LIMIT")
    if not reasons:
        reasons.append("PAPER_STRESS_APPROVED")
    captured = datetime.now(tz=UTC)
    digest = sha256(f"{captured.isoformat()}|{total_notional}|{highest}".encode()).hexdigest()[:24]
    return PaperStressSnapshot(
        stress_id=f"stress-{digest}",
        captured_at=captured,
        portfolio_equity_usd=portfolio.equity_usd,
        stressed_loss_usd=stressed_loss,
        maximum_correlation=highest,
        concentration_fraction=concentration,
        approved=approved,
        reason_codes=tuple(reasons),
    )


def _correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    size = min(len(left), len(right), 60)
    if size < 10:
        return None
    x = [float(value) for value in left[-size:]]
    y = [float(value) for value in right[-size:]]
    x_mean = sum(x) / size
    y_mean = sum(y) / size
    numerator = sum((a - x_mean) * (b - y_mean) for a, b in zip(x, y, strict=True))
    x_scale = sqrt(sum((a - x_mean) ** 2 for a in x))
    y_scale = sqrt(sum((b - y_mean) ** 2 for b in y))
    if x_scale == 0 or y_scale == 0:
        return None
    return numerator / (x_scale * y_scale)
