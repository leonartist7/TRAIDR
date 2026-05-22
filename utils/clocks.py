"""UTC clock and freshness helpers for fail-closed data checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TypeAlias

from utils.results import Result

TimestampInput: TypeAlias = datetime | str | None


@dataclass(frozen=True)
class Freshness:
    """Freshness metadata for a validated UTC observation timestamp."""

    observed_at: datetime
    checked_at: datetime
    age: timedelta


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(timezone.utc)


def parse_utc_timestamp(value: TimestampInput) -> Result[datetime]:
    """Parse a timestamp and reject missing, malformed, or naive values."""

    if value is None:
        return Result.insufficient_data("TIMESTAMP_MISSING")

    parsed: datetime
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return Result.insufficient_data("TIMESTAMP_MISSING")
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            return Result.insufficient_data("TIMESTAMP_MALFORMED")
    else:
        return Result.insufficient_data("TIMESTAMP_MALFORMED")

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return Result.insufficient_data("TIMESTAMP_TIMEZONE_REQUIRED")

    return Result.success(parsed.astimezone(timezone.utc))


def check_freshness(
    observed_at: TimestampInput,
    *,
    max_age: timedelta,
    now: TimestampInput | None = None,
    max_future_skew: timedelta = timedelta(seconds=5),
) -> Result[Freshness]:
    """Validate observation age without treating uncertainty as freshness."""

    if max_age <= timedelta(0) or max_future_skew < timedelta(0):
        return Result.rejected("FRESHNESS_WINDOW_INVALID")

    observed_result = parse_utc_timestamp(observed_at)
    if not observed_result.ok:
        return Result.insufficient_data(*observed_result.reason_codes)

    checked_result = (
        Result.success(utc_now()) if now is None else parse_utc_timestamp(now)
    )
    if not checked_result.ok:
        return Result.insufficient_data(
            "FRESHNESS_CHECK_TIME_INVALID",
            *checked_result.reason_codes,
        )

    observed = observed_result.value
    checked = checked_result.value
    if observed is None or checked is None:
        return Result.insufficient_data("FRESHNESS_TIMESTAMP_UNAVAILABLE")

    age = checked - observed
    if age < -max_future_skew:
        return Result.insufficient_data("TIMESTAMP_IN_FUTURE")
    if age > max_age:
        return Result.insufficient_data("TIMESTAMP_STALE")

    return Result.success(
        Freshness(
            observed_at=observed,
            checked_at=checked,
            age=max(age, timedelta(0)),
        )
    )

