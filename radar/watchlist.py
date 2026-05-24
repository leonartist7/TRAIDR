"""Watchlist normalization for opportunity radar."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def normalize_watchlist(records: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    normalized: list[dict[str, Any]] = []
    for record in records:
        subject_id = str(record.get("subject_id") or record.get("pair_id") or "").strip()
        if not subject_id:
            continue
        normalized.append(
            {
                "subject_id": subject_id,
                "analyses": tuple(record.get("analyses") or ()),
                "macro_context": dict(record.get("macro_context") or {}),
                "news_context": dict(record.get("news_context") or {}),
            }
        )
    return tuple(normalized)

