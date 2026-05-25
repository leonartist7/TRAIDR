"""Service layer for manual local portfolio tracking."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from portfolio.exposure import build_portfolio_report
from portfolio.models import ManualPortfolioEntry, PortfolioReport
from portfolio.repository import PortfolioRepository


class PortfolioService:
    def __init__(self, repository: PortfolioRepository) -> None:
        self.repository = repository

    def add(
        self,
        *,
        symbol: str,
        entry_price: Decimal,
        size_usd: Decimal,
        thesis: str,
        chain: str = "unknown",
        pair_ref: str | None = None,
        stop_zone: str = "",
        take_profit_zone: str = "",
        conviction: str = "medium",
        risk_level: str = "unknown",
        notes: str = "",
        now: datetime | None = None,
    ) -> ManualPortfolioEntry:
        return self.repository.add_entry(
            symbol=symbol,
            chain=chain,
            pair_ref=pair_ref or symbol,
            entry_price=entry_price,
            size_usd=size_usd,
            thesis=thesis,
            stop_zone=stop_zone,
            take_profit_zone=take_profit_zone,
            conviction=conviction,
            risk_level=risk_level,
            notes=notes,
            created_at=now,
        )

    def remove(self, entry_id: str) -> bool:
        return self.repository.deactivate_entry(entry_id)

    def list(self) -> tuple[ManualPortfolioEntry, ...]:
        return self.repository.list_entries(active_only=True)

    def report(self, *, now: datetime | None = None) -> PortfolioReport:
        return build_portfolio_report(self.list(), now=now)
