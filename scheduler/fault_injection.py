"""Deterministic public-stream fault harness used by shadow certification."""

from __future__ import annotations

import asyncio
import json
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any

from data_pipeline.bitunix_websocket import BitunixPublicStream
from data_pipeline.provider_runtime import ProviderCircuitBreaker
from intelligence.production_models import EventQuality


def run_fault_injections() -> dict[str, bool]:
    now = datetime.now(tz=UTC)
    stream = BitunixPublicStream(("BTCUSDT",), intervals=("1m",))
    payload = {
        "ch": "ticker",
        "symbol": "BTCUSDT",
        "ts": int(now.timestamp() * 1000),
        "data": {"s": "BTCUSDT", "la": "68000"},
    }
    first = stream.parse_message(json.dumps(payload), received_at=now)[0]
    duplicate = stream.parse_message(json.dumps(payload), received_at=now)[0]
    payload["ts"] -= 1
    out_of_order = stream.parse_message(json.dumps(payload), received_at=now)[0]
    malformed_rejected = False
    try:
        stream.parse_message("[]", received_at=now)
    except ValueError:
        malformed_rejected = True
    circuit = ProviderCircuitBreaker("test", "public", failure_threshold=2)
    circuit.failure(retry_after_seconds=1, now=now)
    circuit.failure(retry_after_seconds=1, now=now)
    rate_limit_visible = not circuit.allow(now)
    return {
        "duplicate_event_idempotent": first.idempotency_key == duplicate.idempotency_key,
        "out_of_order_visible": out_of_order.quality is EventQuality.CONTRADICTORY,
        "malformed_frame_rejected": malformed_rejected,
        "rate_limit_circuit_opened": rate_limit_visible,
        "disconnect_recovery_harness": asyncio.run(_disconnect_recovery()),
    }


async def _disconnect_recovery() -> bool:
    now = datetime.now(tz=UTC)
    frame = json.dumps(
        {
            "ch": "ticker",
            "symbol": "BTCUSDT",
            "ts": int(now.timestamp() * 1000),
            "data": {"s": "BTCUSDT", "la": "68000"},
        }
    )
    factory = _Factory(frame)
    stream = BitunixPublicStream(
        ("BTCUSDT",),
        connect_factory=factory,
        maximum_backoff_seconds=0.01,
        receive_timeout_seconds=0.05,
    )
    stop = asyncio.Event()
    received = 0

    async def handler(_: Any) -> None:
        nonlocal received
        received += 1
        stop.set()

    await asyncio.wait_for(stream.run(handler, stop), timeout=2)
    return received == 1 and stream.reconnect_count >= 1 and factory.calls >= 2


class _Socket:
    def __init__(self, frame: str | None) -> None:
        self.frame = frame
        self.sent = False

    async def send(self, _: str) -> None:
        return None

    async def recv(self) -> str:
        if self.frame is None:
            raise ConnectionError("injected disconnect")
        if not self.sent:
            self.sent = True
            return self.frame
        await asyncio.sleep(1)
        return self.frame


class _Context(AbstractAsyncContextManager[_Socket]):
    def __init__(self, socket: _Socket) -> None:
        self.socket = socket

    async def __aenter__(self) -> _Socket:
        return self.socket

    async def __aexit__(self, *_: Any) -> None:
        return None


class _Factory:
    def __init__(self, frame: str) -> None:
        self.frame = frame
        self.calls = 0

    def __call__(self, _: str) -> _Context:
        self.calls += 1
        return _Context(_Socket(None if self.calls == 1 else self.frame))
