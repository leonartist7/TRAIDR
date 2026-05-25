"""DuckDB repository for local watchlists."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import duckdb

from utils.toon import assert_safe_payload
from watchlist.models import WatchEntry, WatchScanRecord


class WatchlistRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def upsert_entry(
        self,
        *,
        pair_ref: str,
        note: str = "",
        tags: tuple[str, ...] = (),
        created_at: datetime | None = None,
    ) -> WatchEntry:
        normalized_pair = _pair_ref(pair_ref)
        now = _aware(created_at or _utc_now())
        existing = self.get_entry(normalized_pair)
        entry_created_at = existing.created_at if existing else now
        self.connection.execute(
            """
            INSERT INTO watchlist_entries (
                pair_ref,
                note,
                tags_json,
                created_at,
                updated_at,
                active
            )
            VALUES (?, ?, ?, ?, ?, TRUE)
            ON CONFLICT (pair_ref) DO UPDATE SET
                note = excluded.note,
                tags_json = excluded.tags_json,
                updated_at = excluded.updated_at,
                active = TRUE
            """,
            [
                normalized_pair,
                str(note or ""),
                _safe_json(list(tags)),
                entry_created_at,
                now,
            ],
        )
        return WatchEntry(normalized_pair, str(note or ""), tuple(tags), entry_created_at, True)

    def deactivate_entry(self, pair_ref: str) -> bool:
        normalized_pair = _pair_ref(pair_ref)
        before = self.connection.execute(
            "SELECT active FROM watchlist_entries WHERE pair_ref = ?",
            [normalized_pair],
        ).fetchone()
        if before is None:
            return False
        self.connection.execute(
            """
            UPDATE watchlist_entries
            SET active = FALSE, updated_at = ?
            WHERE pair_ref = ?
            """,
            [_utc_now(), normalized_pair],
        )
        return bool(before[0])

    def get_entry(self, pair_ref: str) -> WatchEntry | None:
        row = self.connection.execute(
            """
            SELECT pair_ref, note, tags_json, created_at, active
            FROM watchlist_entries
            WHERE pair_ref = ?
            """,
            [_pair_ref(pair_ref)],
        ).fetchone()
        return _entry_from_row(row) if row else None

    def list_entries(self, *, active_only: bool = True) -> tuple[WatchEntry, ...]:
        where = "WHERE active = TRUE" if active_only else ""
        rows = self.connection.execute(
            f"""
            SELECT pair_ref, note, tags_json, created_at, active
            FROM watchlist_entries
            {where}
            ORDER BY created_at DESC
            """
        ).fetchall()
        return tuple(_entry_from_row(row) for row in rows)

    def record_scan_result(self, record: WatchScanRecord) -> str:
        scan_id = f"watch_scan_{uuid4().hex}"
        payload = record.to_dict()
        self.connection.execute(
            """
            INSERT INTO watchlist_scan_results (
                scan_id,
                pair_ref,
                scanned_at,
                status,
                radar_state,
                opportunity_score,
                risk_score,
                reason_codes_json,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                scan_id,
                record.pair_ref,
                _aware(record.scanned_at),
                record.status,
                record.radar_state,
                record.opportunity_score,
                record.risk_score,
                _safe_json(list(record.reason_codes)),
                _safe_json(payload),
            ],
        )
        return scan_id

    def latest_scan_for(self, pair_ref: str) -> WatchScanRecord | None:
        row = self.connection.execute(
            """
            SELECT pair_ref, scanned_at, status, radar_state, opportunity_score, risk_score, reason_codes_json
            FROM watchlist_scan_results
            WHERE pair_ref = ?
            ORDER BY scanned_at DESC
            LIMIT 1
            """,
            [_pair_ref(pair_ref)],
        ).fetchone()
        return _scan_from_row(row) if row else None


def _entry_from_row(row: tuple[Any, ...]) -> WatchEntry:
    return WatchEntry(
        pair_ref=str(row[0]),
        note=str(row[1]),
        tags=tuple(str(tag) for tag in _json_list(row[2])),
        created_at=_from_db_time(row[3]),
        active=bool(row[4]),
    )


def _scan_from_row(row: tuple[Any, ...]) -> WatchScanRecord:
    return WatchScanRecord(
        pair_ref=str(row[0]),
        scanned_at=_from_db_time(row[1]),
        status=str(row[2]),
        radar_state=str(row[3]),
        opportunity_score=float(row[4]),
        risk_score=float(row[5]),
        reason_codes=tuple(str(reason) for reason in _json_list(row[6])),
    )


def _pair_ref(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("watchlist pair_ref is required")
    return text


def _safe_json(value: Any) -> str:
    assert_safe_payload(value)
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _json_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _from_db_time(value: datetime) -> datetime:
    return _aware(value)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
