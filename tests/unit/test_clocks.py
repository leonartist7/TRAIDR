from datetime import datetime, timedelta, timezone

from utils.clocks import check_freshness, parse_utc_timestamp
from utils.results import ResultStatus


def test_freshness_accepts_recent_aware_timestamp() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    result = check_freshness(
        "2026-05-22T11:59:30Z",
        max_age=timedelta(minutes=1),
        now=now,
    )

    assert result.ok is True
    assert result.value is not None
    assert result.value.age == timedelta(seconds=30)


def test_freshness_fails_closed_for_stale_timestamp() -> None:
    result = check_freshness(
        "2026-05-22T11:00:00+00:00",
        max_age=timedelta(minutes=5),
        now="2026-05-22T12:00:00+00:00",
    )

    assert result.status is ResultStatus.INSUFFICIENT_DATA
    assert result.reason_codes == ("TIMESTAMP_STALE",)


def test_parse_timestamp_rejects_malformed_or_naive_values() -> None:
    malformed = parse_utc_timestamp("not-a-timestamp")
    naive = parse_utc_timestamp("2026-05-22T12:00:00")

    assert malformed.reason_codes == ("TIMESTAMP_MALFORMED",)
    assert naive.reason_codes == ("TIMESTAMP_TIMEZONE_REQUIRED",)

