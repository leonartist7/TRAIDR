"""Final deterministic gate for local perpetual-futures paper simulation."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from execution.paper_futures import PaperFuturesLimits, PaperPortfolioSnapshot
from intelligence.production_models import RiskAssessment, SignalDecision, SignalDirection


def assess_paper_signal(
    signal: SignalDecision,
    portfolio: PaperPortfolioSnapshot,
    *,
    limits: PaperFuturesLimits,
    market_fresh: bool,
    depth_available: bool,
    mark_index_available: bool,
    correlation_exposure_ok: bool = True,
    simultaneous_loss_stress_ok: bool = True,
    now: datetime | None = None,
) -> RiskAssessment:
    """Approve only complete, cost-positive, bounded research signals for paper use."""

    decided_at = now or datetime.now(tz=UTC)
    checks = {
        "direction_actionable": signal.direction is not SignalDirection.NO_TRADE,
        "no_hard_veto": not signal.hard_vetoes,
        "signal_unexpired": signal.expires_at > decided_at,
        "data_coverage": signal.data_coverage >= 0.75,
        "market_fresh": market_fresh,
        "depth_available": depth_available,
        "mark_index_available": mark_index_available,
        "bracket_complete": signal.stop is not None and bool(signal.targets),
        "risk_reward": signal.risk_reward is not None and signal.risk_reward >= 1.5,
        "expected_return_after_costs": signal.expected_return_pct is not None
        and signal.expected_return_pct > 0,
        "risk_grade": signal.risk_score <= 60,
        "daily_drawdown": not portfolio.halted,
        "position_count": len(portfolio.open_positions) < limits.maximum_positions,
        "margin_allocation": portfolio.used_margin_usd
        < portfolio.equity_usd * limits.maximum_margin_fraction,
        "correlation_exposure": correlation_exposure_ok,
        "simultaneous_loss_stress": simultaneous_loss_stress_ok,
    }
    assessment_id = _assessment_id(signal, decided_at)
    missing_checks = {
        "market_fresh",
        "depth_available",
        "mark_index_available",
        "bracket_complete",
    }
    missing = tuple(name for name in missing_checks if not checks[name])
    if missing:
        return RiskAssessment(
            assessment_id=assessment_id,
            signal_id=signal.signal_id,
            outcome="INSUFFICIENT_DATA",
            decided_at=decided_at,
            reason_codes=tuple(f"PAPER_{name.upper()}_REQUIRED" for name in sorted(missing)),
            limit_checks=checks,
        )
    failed = tuple(name for name, passed in checks.items() if not passed)
    if failed:
        reasons = list(signal.hard_vetoes)
        reasons.extend(f"PAPER_{name.upper()}_VETO" for name in failed)
        return RiskAssessment(
            assessment_id=assessment_id,
            signal_id=signal.signal_id,
            outcome="HOLD",
            decided_at=decided_at,
            reason_codes=tuple(dict.fromkeys(reasons)),
            limit_checks=checks,
        )
    return RiskAssessment(
        assessment_id=assessment_id,
        signal_id=signal.signal_id,
        outcome="APPROVED_PAPER",
        decided_at=decided_at,
        approved_leverage=limits.default_leverage,
        approved_notional_usd=None,
        reason_codes=("DETERMINISTIC_PAPER_RISK_APPROVED", "NO_EXCHANGE_EXECUTION"),
        limit_checks=checks,
    )


def _assessment_id(signal: SignalDecision, decided_at: datetime) -> str:
    digest = sha256(
        f"{signal.signal_id}|{decided_at.isoformat()}|paper-risk-v1".encode("utf-8")
    ).hexdigest()[:24]
    return f"paper-risk-{digest}"
