"""Supervised read-only Bitunix public WebSocket client with injectable transport."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, AsyncContextManager, Protocol

from intelligence.production_models import DataMode, EventQuality, MarketChannel, MarketEvent

BITUNIX_PUBLIC_WEBSOCKET_URL = "wss://fapi.bitunix.com/public/"
PUBLIC_CHANNELS = frozenset({"ticker", "tickers", "trade", "price", "depth_book1", "depth_book5", "depth_book15"})
INTERVAL_CHANNELS = {
    "1m": "market_kline_1min",
    "5m": "market_kline_5min",
    "15m": "market_kline_15min",
    "1h": "market_kline_60min",
    "4h": "market_kline_4h",
    "1d": "market_kline_1day",
}


class PublicWebSocket(Protocol):
    async def send(self, message: str) -> None: ...
    async def recv(self) -> str | bytes: ...


ConnectFactory = Callable[[str], AsyncContextManager[PublicWebSocket]]
EventHandler = Callable[[MarketEvent], Awaitable[None]]
HealthHandler = Callable[[str, int, int, tuple[str, ...]], Awaitable[None]]


class BitunixPublicStream:
    """Reconnect public streams forever until the supplied stop event is set."""

    def __init__(
        self,
        symbols: Sequence[str],
        *,
        intervals: Sequence[str] = ("1m",),
        include_channels: Sequence[str] = ("ticker", "depth_book15", "trade", "price"),
        connect_factory: ConnectFactory | None = None,
        url: str = BITUNIX_PUBLIC_WEBSOCKET_URL,
        ping_interval_seconds: float = 20.0,
        receive_timeout_seconds: float = 35.0,
        maximum_backoff_seconds: float = 30.0,
    ) -> None:
        normalized_symbols = tuple(dict.fromkeys(symbol.upper().strip() for symbol in symbols if symbol.strip()))
        if not normalized_symbols:
            raise ValueError("public stream requires at least one symbol")
        channels = tuple(dict.fromkeys(include_channels))
        if any(channel not in PUBLIC_CHANNELS for channel in channels):
            raise ValueError("unsupported or non-public Bitunix channel")
        if any(interval not in INTERVAL_CHANNELS for interval in intervals):
            raise ValueError("unsupported Bitunix stream interval")
        requested = len(normalized_symbols) * (len(channels) + len(tuple(intervals)))
        if requested > 300:
            raise ValueError("Bitunix public connection subscription limit exceeded")
        self.symbols = normalized_symbols
        self.intervals = tuple(intervals)
        self.channels = channels
        self.connect_factory = connect_factory or _default_connect
        self.url = url
        self.ping_interval_seconds = ping_interval_seconds
        self.receive_timeout_seconds = receive_timeout_seconds
        self.maximum_backoff_seconds = maximum_backoff_seconds
        self.reconnect_count = 0
        self.gap_count = 0
        self._last_timestamp: dict[tuple[str, str], int] = {}

    def subscription_request(self) -> dict[str, Any]:
        args = [
            {"symbol": symbol, "ch": channel}
            for symbol in self.symbols
            for channel in (*self.channels, *(INTERVAL_CHANNELS[interval] for interval in self.intervals))
        ]
        return {"op": "subscribe", "args": args}

    async def run(
        self,
        handler: EventHandler,
        stop_event: asyncio.Event,
        *,
        health_handler: HealthHandler | None = None,
    ) -> None:
        backoff = 1.0
        while not stop_event.is_set():
            try:
                async with self.connect_factory(self.url) as websocket:
                    await websocket.send(json.dumps(self.subscription_request(), separators=(",", ":")))
                    if health_handler is not None:
                        await health_handler("HEALTHY", self.reconnect_count, self.gap_count, ("BITUNIX_WS_CONNECTED",))
                    backoff = 1.0
                    await self._receive_loop(websocket, handler, stop_event)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.reconnect_count += 1
                if health_handler is not None:
                    await health_handler(
                        "DEGRADED",
                        self.reconnect_count,
                        self.gap_count,
                        ("BITUNIX_WS_DISCONNECTED", "RECONNECT_SCHEDULED"),
                    )
                if stop_event.is_set():
                    break
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=backoff)
                except TimeoutError:
                    pass
                backoff = min(self.maximum_backoff_seconds, backoff * 2.0)

    async def _receive_loop(
        self,
        websocket: PublicWebSocket,
        handler: EventHandler,
        stop_event: asyncio.Event,
    ) -> None:
        last_ping = asyncio.get_running_loop().time()
        while not stop_event.is_set():
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=self.receive_timeout_seconds)
            except TimeoutError:
                now = int(datetime.now(tz=UTC).timestamp())
                await websocket.send(json.dumps({"op": "ping", "ping": now}, separators=(",", ":")))
                last_ping = asyncio.get_running_loop().time()
                continue
            for event in self.parse_message(message):
                await handler(event)
            if asyncio.get_running_loop().time() - last_ping >= self.ping_interval_seconds:
                now = int(datetime.now(tz=UTC).timestamp())
                await websocket.send(json.dumps({"op": "ping", "ping": now}, separators=(",", ":")))
                last_ping = asyncio.get_running_loop().time()

    def parse_message(self, message: str | bytes, *, received_at: datetime | None = None) -> tuple[MarketEvent, ...]:
        received = received_at or datetime.now(tz=UTC)
        if isinstance(message, bytes):
            message = message.decode("utf-8")
        raw = json.loads(message)
        if not isinstance(raw, Mapping):
            raise ValueError("Bitunix WebSocket frame must be an object")
        if "pong" in raw or raw.get("event") in {"subscribe", "unsubscribe"} or "ch" not in raw:
            return ()
        channel_name = str(raw.get("ch", ""))
        symbol = str(raw.get("symbol") or "").upper()
        data = raw.get("data")
        if channel_name == "tickers" and isinstance(data, list):
            return tuple(
                self._event_from_payload(
                    channel_name,
                    str(item.get("s", "")).upper(),
                    raw.get("ts"),
                    item,
                    received,
                )
                for item in data
                if isinstance(item, Mapping) and item.get("s")
            )
        if not symbol or not isinstance(data, (Mapping, list)):
            raise ValueError("Bitunix WebSocket frame is missing symbol or data")
        return (self._event_from_payload(channel_name, symbol, raw.get("ts"), data, received),)

    def _event_from_payload(
        self,
        channel_name: str,
        symbol: str,
        timestamp: Any,
        payload: Mapping[str, Any] | list[Any],
        received_at: datetime,
    ) -> MarketEvent:
        timestamp_ms = int(timestamp)
        event_at = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
        key = (symbol, channel_name)
        quality = EventQuality.SUFFICIENT
        reasons = ["BITUNIX_PUBLIC_WS", "NO_EXECUTION_ACTION"]
        previous = self._last_timestamp.get(key)
        if previous is not None and timestamp_ms < previous:
            quality = EventQuality.CONTRADICTORY
            reasons.append("BITUNIX_WS_OUT_OF_ORDER")
            self.gap_count += 1
        self._last_timestamp[key] = max(timestamp_ms, previous or timestamp_ms)
        normalized_payload = _json_value(payload)
        schema_fingerprint = _schema_fingerprint(normalized_payload)
        digest = sha256(
            json.dumps(
                [symbol, channel_name, timestamp_ms, normalized_payload],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:32]
        return MarketEvent(
            event_id=f"bitunix-ws-{digest}",
            idempotency_key=f"bitunix:{symbol}:{channel_name}:{digest}",
            data_mode=DataMode.LIVE_PUBLIC,
            source="bitunix_public_ws",
            instrument_id=f"bitunix:{symbol}",
            channel=_market_channel(channel_name),
            event_at=event_at,
            received_at=received_at,
            sequence=None,
            payload_version="bitunix-public-ws-v1",
            schema_fingerprint=schema_fingerprint,
            quality=quality,
            reason_codes=tuple(reasons),
            payload={"channel": channel_name, "symbol": symbol, "data": normalized_payload},
        )


def _market_channel(channel: str) -> MarketChannel:
    if "kline" in channel:
        return MarketChannel.KLINE
    if channel.startswith("depth"):
        return MarketChannel.DEPTH
    if channel in {"ticker", "tickers"}:
        return MarketChannel.TICKER
    if channel == "trade":
        return MarketChannel.TRADE
    if channel == "price":
        return MarketChannel.PRICE
    raise ValueError("unknown Bitunix public channel")


def _schema_fingerprint(payload: Any) -> str:
    def shape(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: shape(item) for key, item in sorted(value.items())}
        if isinstance(value, list):
            return [shape(value[0])] if value else []
        return type(value).__name__

    return sha256(json.dumps(shape(payload), sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("Bitunix WebSocket payload contains unsupported values")


def _default_connect(url: str) -> AsyncContextManager[PublicWebSocket]:
    from websockets.asyncio.client import connect

    return connect(url, open_timeout=10, close_timeout=5, ping_interval=None, max_size=2**20)
