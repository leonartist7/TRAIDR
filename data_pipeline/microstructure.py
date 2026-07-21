"""One-minute public order-book and aggressive trade-flow aggregation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Any, Mapping

from intelligence.production_models import MarketChannel, MarketEvent


@dataclass(frozen=True)
class MicrostructureMinute:
    metric_id: str
    instrument_id: str
    observed_at: datetime
    bid_price: Decimal | None
    ask_price: Decimal | None
    spread_bps: float | None
    depth_imbalance: float | None
    trade_delta: float
    absorption: float
    liquidity_concentration: float | None
    resilience: float | None


class MicrostructureAccumulator:
    def __init__(self) -> None:
        self._trade_delta: dict[tuple[str, int], Decimal] = defaultdict(lambda: Decimal("0"))
        self._last_spread: dict[str, float] = {}

    def ingest(self, event: MarketEvent) -> MicrostructureMinute | None:
        minute_ms = int(event.event_at.timestamp() * 1000) // 60_000 * 60_000
        key = (event.instrument_id, minute_ms)
        if event.channel is MarketChannel.TRADE:
            for trade in _rows(event.payload.get("data")):
                size = _decimal(trade.get("q") or trade.get("volume") or trade.get("v"))
                side = str(trade.get("side") or trade.get("S") or "").upper()
                self._trade_delta[key] += size if side in {"BUY", "B"} else -size
            return None
        if event.channel is not MarketChannel.DEPTH:
            return None
        payload = event.payload.get("data")
        if not isinstance(payload, Mapping):
            return None
        bids = _levels(payload.get("bids") or payload.get("b"))
        asks = _levels(payload.get("asks") or payload.get("a"))
        if not bids or not asks:
            return None
        bid, ask = bids[0][0], asks[0][0]
        midpoint = (bid + ask) / Decimal("2")
        spread = float((ask - bid) / midpoint * Decimal("10000")) if midpoint > 0 else None
        bid_depth = sum((row[1] for row in bids), Decimal("0"))
        ask_depth = sum((row[1] for row in asks), Decimal("0"))
        total_depth = bid_depth + ask_depth
        imbalance = float((bid_depth - ask_depth) / total_depth) if total_depth > 0 else None
        largest = max((row[1] for row in (*bids, *asks)), default=Decimal("0"))
        concentration = float(largest / total_depth) if total_depth > 0 else None
        previous_spread = self._last_spread.get(event.instrument_id)
        resilience = None if previous_spread is None or spread is None else previous_spread - spread
        if spread is not None:
            self._last_spread[event.instrument_id] = spread
        delta = self._trade_delta.pop(key, Decimal("0"))
        absorption = float(abs(delta) / total_depth) if total_depth > 0 else 0.0
        digest = sha256(f"{event.instrument_id}|{minute_ms}|micro-v1".encode()).hexdigest()[:24]
        return MicrostructureMinute(
            metric_id=f"micro-{digest}",
            instrument_id=event.instrument_id,
            observed_at=datetime.fromtimestamp(minute_ms / 1000, tz=UTC),
            bid_price=bid,
            ask_price=ask,
            spread_bps=spread,
            depth_imbalance=imbalance,
            trade_delta=float(delta),
            absorption=absorption,
            liquidity_concentration=concentration,
            resilience=resilience,
        )


def _rows(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list):
        return tuple(row for row in value if isinstance(row, Mapping))
    return ()


def _levels(value: Any) -> tuple[tuple[Decimal, Decimal], ...]:
    rows: list[tuple[Decimal, Decimal]] = []
    if not isinstance(value, list):
        return ()
    for row in value:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            rows.append((_decimal(row[0]), _decimal(row[1])))
        elif isinstance(row, Mapping):
            rows.append((_decimal(row.get("price") or row.get("p")), _decimal(row.get("volume") or row.get("q"))))
    return tuple(item for item in rows if item[0] > 0 and item[1] >= 0)


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception:
        return Decimal("0")
