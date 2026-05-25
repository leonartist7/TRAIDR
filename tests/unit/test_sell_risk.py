from datetime import datetime, timezone
from decimal import Decimal

from portfolio.models import ManualPortfolioEntry
from portfolio.sell_risk import PositionEvidence, SellRiskState, evaluate_sell_risk

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
OLD = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)


def test_sell_risk_holds_when_evidence_is_clean() -> None:
    decision = evaluate_sell_risk(
        _entry(updated_at=NOW),
        PositionEvidence(
            current_price_usd=Decimal("1.20"),
            current_liquidity_usd=Decimal("10000"),
            previous_liquidity_usd=Decimal("10000"),
            risk_score=20,
            previous_risk_score=20,
            radar_state="WATCH",
            opportunity_score=70,
            previous_opportunity_score=65,
            token_safety_complete=True,
        ),
        now=NOW,
    )

    assert decision.state is SellRiskState.HOLD_POSITION
    assert decision.can_execute_trades is False


def test_sell_risk_marks_exit_candidate_for_compounding_risks() -> None:
    decision = evaluate_sell_risk(
        _entry(stop_zone="below 0.90", updated_at=OLD),
        PositionEvidence(
            current_price_usd=Decimal("0.80"),
            current_liquidity_usd=Decimal("4000"),
            previous_liquidity_usd=Decimal("10000"),
            risk_score=90,
            previous_risk_score=40,
            radar_state="AVOID",
            opportunity_score=20,
            previous_opportunity_score=80,
            token_safety_complete=False,
            macro_news_classification="RISK_OFF",
        ),
        now=NOW,
    )

    assert decision.state is SellRiskState.EXIT_CANDIDATE
    assert "LIQUIDITY_DRAIN" in decision.reason_codes
    assert "STOP_ZONE_REACHED" in decision.reason_codes
    assert "NO_EXECUTION_ACTION" in decision.reason_codes


def test_sell_risk_returns_insufficient_data_when_core_evidence_missing() -> None:
    decision = evaluate_sell_risk(
        _entry(updated_at=NOW),
        PositionEvidence(),
        now=NOW,
    )

    assert decision.state is SellRiskState.INSUFFICIENT_DATA
    assert "RISK_SCORE_MISSING" in decision.reason_codes


def _entry(*, stop_zone: str = "below 0.50", updated_at: datetime) -> ManualPortfolioEntry:
    return ManualPortfolioEntry(
        entry_id="manual_portfolio_test",
        symbol="BONK",
        chain="solana",
        pair_ref="solana/BONK",
        entry_price=Decimal("1.00"),
        size_usd=Decimal("20"),
        thesis="meme momentum",
        stop_zone=stop_zone,
        take_profit_zone="2x",
        conviction="medium",
        risk_level="high",
        notes="",
        created_at=updated_at,
        updated_at=updated_at,
        active=True,
    )
