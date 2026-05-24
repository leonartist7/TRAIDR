"""Small text formatters for terminal-friendly TRAIDR output."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def section(title: str, lines: Iterable[str] = ()) -> str:
    body = [title, "-" * len(title)]
    body.extend(lines)
    return "\n".join(body)


def key_values(values: Mapping[str, Any]) -> str:
    return "\n".join(f"{key}: {_render(value)}" for key, value in values.items())


def records_table(records: Sequence[Mapping[str, Any]], *, empty: str = "No records found.") -> str:
    if not records:
        return empty
    columns = tuple(records[0].keys())
    widths = {
        column: max(len(str(column)), *(len(_render(record.get(column))) for record in records))
        for column in columns
    }
    header = " | ".join(str(column).ljust(widths[column]) for column in columns)
    divider = "-+-".join("-" * widths[column] for column in columns)
    rows = [
        " | ".join(_render(record.get(column)).ljust(widths[column]) for column in columns)
        for record in records
    ]
    return "\n".join((header, divider, *rows))


def bullet_list(items: Iterable[Any], *, empty: str = "- none") -> str:
    rows = [f"- {_render(item)}" for item in items]
    return "\n".join(rows) if rows else empty


def _render(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, list | tuple):
        return ", ".join(_render(item) for item in value)
    if value is None:
        return "none"
    return str(value)

