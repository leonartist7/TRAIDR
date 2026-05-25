from datetime import datetime, timezone
from decimal import Decimal

from portfolio.exposure import build_portfolio_report
from portfolio.models import ManualPortfolioEntry

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
OLD = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)


def test_portfolio_exposure_report_calculates_totals_and_concentration() -> None:
    report = build_portfolio_report(
        (
            _entry("one", "BONK", "solana", Decimal("70"), "meme thesis", updated_at=NOW),
            _entry("two", "ETH", "ethereum", Decimal("30"), "core thesis", updated_at=NOW),
        ),
        now=NOW,
    )

    assert report.total_exposure_usd == Decimal("100")
    assert report.concentration_risk == "high"
    assert report.meme_exposure_usd == Decimal("70")
    assert report.chain_exposure == {"ethereum": "30", "solana": "70"}
    assert report.can_execute_trades is False


def test_portfolio_exposure_warns_on_missing_and_stale_thesis() -> None:
    report = build_portfolio_report(
        (
            _entry(
                "stale",
                "ABC",
                "solana",
                Decimal("20"),
                "",
                stop_zone="",
                conviction="high",
                risk_level="unknown",
                updated_at=OLD,
            ),
        ),
        now=NOW,
    )

    assert any("THESIS_MISSING" in warning for warning in report.thesis_warnings)
    assert any("STOP_ZONE_MISSING" in warning for warning in report.thesis_warnings)
    assert any("HIGH_CONVICTION" in warning for warning in report.thesis_warnings)
    assert any("THESIS_STALE" in warning for warning in report.stale_thesis_warnings)


def _entry(
    entry_id: str,
    symbol: str,
    chain: str,
    size: Decimal,
    thesis: str,
    *,
    stop_zone: str = "below support",
    conviction: str = "medium",
    risk_level: str = "medium",
    updated_at: datetime,
) -> ManualPortfolioEntry:
    return ManualPortfolioEntry(
        entry_id=entry_id,
        symbol=symbol,
        chain=chain,
        pair_ref=f"{chain}/{symbol}",
        entry_price=Decimal("0.01"),
        size_usd=size,
        thesis=thesis,
        stop_zone=stop_zone,
        take_profit_zone="2x",
        conviction=conviction,
        risk_level=risk_level,
        notes="",
        created_at=updated_at,
        updated_at=updated_at,
        active=True,
    )
