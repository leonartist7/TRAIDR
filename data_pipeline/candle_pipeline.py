"""Normalize one-minute WebSocket candles, detect gaps, and aggregate deterministically."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Any, Mapping, Sequence

from data_pipeline.bitunix_models import BitunixCandle
from intelligence.production_models import IngestionGap, IngestionGapStatus, MarketEvent


HORIZON_MINUTES = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def candle_from_ws_event(event: MarketEvent) -> BitunixCandle:
    if event.channel.value != "kline":
        raise ValueError("event is not a candle")
    payload = event.payload.get("data")
    if isinstance(payload, list):
        payload = payload[0] if payload and isinstance(payload[0], Mapping) else None
    if not isinstance(payload, Mapping):
        raise ValueError("WebSocket candle payload is malformed")
    symbol = str(event.payload.get("symbol") or event.instrument_id.split(":", 1)[-1])
    interval = _channel_interval(str(event.payload.get("channel") or ""))
    timestamp = _first(payload, "t", "time", "ts", "openTime")
    if timestamp is None:
        timestamp = int(event.event_at.timestamp() * 1000)
    timestamp = int(timestamp)
    if timestamp < 10_000_000_000:
        timestamp *= 1000
    return BitunixCandle(
        symbol=symbol,
        interval=interval,
        time_ms=timestamp,
        open=_first(payload, "o", "open"),
        high=_first(payload, "h", "high"),
        low=_first(payload, "l", "low"),
        close=_first(payload, "c", "close"),
        quote_volume=_first(payload, "q", "quoteVol", "quoteVolume", default="0"),
        base_volume=_first(payload, "b", "baseVol", "volume", default="0"),
    )


def aggregate_candles(
    candles: Sequence[BitunixCandle],
    horizon: str,
    *,
    require_complete: bool = True,
) -> tuple[BitunixCandle, ...]:
    minutes = HORIZON_MINUTES[horizon]
    bucket_ms = minutes * 60_000
    groups: dict[int, list[BitunixCandle]] = defaultdict(list)
    for candle in sorted(candles, key=lambda item: item.time_ms):
        groups[candle.time_ms // bucket_ms * bucket_ms].append(candle)
    rows: list[BitunixCandle] = []
    for bucket, items in sorted(groups.items()):
        expected_times = {bucket + offset * 60_000 for offset in range(minutes)}
        actual_times = {item.time_ms for item in items}
        if require_complete and actual_times != expected_times:
            continue
        rows.append(
            BitunixCandle(
                symbol=items[0].symbol,
                interval=horizon,
                time_ms=bucket,
                open=items[0].open,
                high=max(item.high for item in items),
                low=min(item.low for item in items),
                close=items[-1].close,
                quote_volume=sum((item.quote_volume for item in items), Decimal("0")),
                base_volume=sum((item.base_volume for item in items), Decimal("0")),
            )
        )
    return tuple(rows)


class OneMinuteCandlePipeline:
    def __init__(self) -> None:
        self._last_open_ms: dict[str, int] = {}

    def ingest(self, event: MarketEvent) -> tuple[BitunixCandle, IngestionGap | None]:
        candle = candle_from_ws_event(event)
        previous = self._last_open_ms.get(event.instrument_id)
        gap = None
        if previous is not None and candle.time_ms > previous + 60_000:
            start = datetime.fromtimestamp((previous + 60_000) / 1000, tz=UTC)
            end = datetime.fromtimestamp((candle.time_ms - 60_000) / 1000, tz=UTC)
            digest = sha256(f"{event.instrument_id}|1m|{start.isoformat()}|{end.isoformat()}".encode()).hexdigest()[:24]
            gap = IngestionGap(
                gap_id=f"gap-{digest}",
                idempotency_key=f"bitunix:{event.instrument_id}:1m:{digest}",
                source="bitunix_public_ws",
                instrument_id=event.instrument_id,
                channel=event.channel,
                interval="1m",
                detected_at=event.received_at,
                gap_start=start,
                gap_end=end,
                status=IngestionGapStatus.DETECTED,
                updated_at=event.received_at,
                reason_codes=("ONE_MINUTE_SEQUENCE_GAP", "REST_BACKFILL_REQUIRED"),
            )
        self._last_open_ms[event.instrument_id] = max(previous or 0, candle.time_ms)
        return candle, gap


def expected_one_minute_range(start: datetime, end: datetime) -> tuple[int, ...]:
    cursor = start.astimezone(UTC).replace(second=0, microsecond=0)
    finish = end.astimezone(UTC).replace(second=0, microsecond=0)
    rows: list[int] = []
    while cursor <= finish:
        rows.append(int(cursor.timestamp() * 1000))
        cursor += timedelta(minutes=1)
    return tuple(rows)


def _channel_interval(channel: str) -> str:
    if channel.endswith("1min"):
        return "1m"
    raise ValueError("only one-minute WebSocket candles are accepted")


def _first(payload: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if payload.get(key) is not None:
            return payload[key]
    return default
