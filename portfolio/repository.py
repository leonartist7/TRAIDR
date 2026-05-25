"""DuckDB repository for manual portfolio entries."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import duckdb

from portfolio.models import ManualPortfolioEntry


class PortfolioRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def add_entry(
        self,
        *,
        symbol: str,
        chain: str,
        pair_ref: str,
        entry_price: Decimal,
        size_usd: Decimal,
        thesis: str,
        stop_zone: str = "",
        take_profit_zone: str = "",
        conviction: str = "medium",
        risk_level: str = "unknown",
        notes: str = "",
        created_at: datetime | None = None,
    ) -> ManualPortfolioEntry:
        now = _aware(created_at or datetime.now(timezone.utc))
        entry = ManualPortfolioEntry(
            entry_id=f"manual_portfolio_{uuid4().hex}",
            symbol=_text(symbol).upper(),
            chain=_text(chain or "unknown").lower(),
            pair_ref=_text(pair_ref or symbol),
            entry_price=_positive_decimal(entry_price, "entry_price"),
            size_usd=_positive_decimal(size_usd, "size_usd"),
            thesis=str(thesis or ""),
            stop_zone=str(stop_zone or ""),
            take_profit_zone=str(take_profit_zone or ""),
            conviction=str(conviction or "medium").lower(),
            risk_level=str(risk_level or "unknown").lower(),
            notes=str(notes or ""),
            created_at=now,
            updated_at=now,
            active=True,
        )
        self.connection.execute(
            """
            INSERT INTO manual_portfolio_entries (
                entry_id,
                symbol,
                chain,
                pair_ref,
                entry_price,
                size_usd,
                thesis,
                stop_zone,
                take_profit_zone,
                conviction,
                risk_level,
                notes,
                created_at,
                updated_at,
                active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE)
            """,
            [
                entry.entry_id,
                entry.symbol,
                entry.chain,
                entry.pair_ref,
                entry.entry_price,
                entry.size_usd,
                entry.thesis,
                entry.stop_zone,
                entry.take_profit_zone,
                entry.conviction,
                entry.risk_level,
                entry.notes,
                entry.created_at,
                entry.updated_at,
            ],
        )
        return entry

    def deactivate_entry(self, entry_id: str) -> bool:
        row = self.connection.execute(
            "SELECT active FROM manual_portfolio_entries WHERE entry_id = ?",
            [entry_id],
        ).fetchone()
        if row is None:
            return False
        self.connection.execute(
            """
            UPDATE manual_portfolio_entries
            SET active = FALSE, updated_at = ?
            WHERE entry_id = ?
            """,
            [datetime.now(timezone.utc), entry_id],
        )
        return bool(row[0])

    def list_entries(self, *, active_only: bool = True) -> tuple[ManualPortfolioEntry, ...]:
        where = "WHERE active = TRUE" if active_only else ""
        rows = self.connection.execute(
            f"""
            SELECT
                entry_id,
                symbol,
                chain,
                pair_ref,
                entry_price,
                size_usd,
                thesis,
                stop_zone,
                take_profit_zone,
                conviction,
                risk_level,
                notes,
                created_at,
                updated_at,
                active
            FROM manual_portfolio_entries
            {where}
            ORDER BY created_at DESC
            """
        ).fetchall()
        return tuple(_entry_from_row(row) for row in rows)


def _entry_from_row(row: tuple[Any, ...]) -> ManualPortfolioEntry:
    return ManualPortfolioEntry(
        entry_id=str(row[0]),
        symbol=str(row[1]),
        chain=str(row[2]),
        pair_ref=str(row[3]),
        entry_price=Decimal(str(row[4])),
        size_usd=Decimal(str(row[5])),
        thesis=str(row[6]),
        stop_zone=str(row[7]),
        take_profit_zone=str(row[8]),
        conviction=str(row[9]),
        risk_level=str(row[10]),
        notes=str(row[11]),
        created_at=_aware(row[12]),
        updated_at=_aware(row[13]),
        active=bool(row[14]),
    )


def _text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("manual portfolio text field is required")
    return text


def _positive_decimal(value: Any, field: str) -> Decimal:
    number = Decimal(str(value))
    if number <= 0:
        raise ValueError(f"{field} must be positive")
    return number


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
