"""Bounded public-provider throttling and deterministic circuit breakers."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from time import monotonic

from intelligence.production_models import CircuitStatus, ProviderCircuitState


class TokenBucket:
    def __init__(self, rate_per_second: float, capacity: int) -> None:
        if rate_per_second <= 0 or capacity < 1:
            raise ValueError("token bucket limits must be positive")
        self.rate = rate_per_second
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.updated = monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait_for = (1 - self.tokens) / self.rate
            await asyncio.sleep(wait_for)


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    if not value:
        return None
    stripped = value.strip()
    try:
        return max(0.0, float(stripped))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(stripped)
        except (TypeError, ValueError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        reference = now or datetime.now(tz=UTC)
        return max(0.0, (retry_at.astimezone(UTC) - reference).total_seconds())


@dataclass
class ProviderCircuitBreaker:
    provider: str
    channel: str
    failure_threshold: int = 5
    recovery_seconds: float = 60.0
    state: CircuitStatus = CircuitStatus.CLOSED
    failure_count: int = 0
    opened_at: datetime | None = None
    retry_after: datetime | None = None

    def allow(self, now: datetime | None = None) -> bool:
        reference = now or datetime.now(tz=UTC)
        if self.state is CircuitStatus.OPEN and self.retry_after and reference >= self.retry_after:
            self.state = CircuitStatus.HALF_OPEN
            return True
        return self.state is not CircuitStatus.OPEN

    def success(self) -> None:
        self.state = CircuitStatus.CLOSED
        self.failure_count = 0
        self.opened_at = None
        self.retry_after = None

    def failure(self, *, retry_after_seconds: float | None = None, now: datetime | None = None) -> None:
        reference = now or datetime.now(tz=UTC)
        self.failure_count += 1
        if self.state is CircuitStatus.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self.state = CircuitStatus.OPEN
            self.opened_at = reference
            delay = retry_after_seconds if retry_after_seconds is not None else self.recovery_seconds
            self.retry_after = reference + timedelta(seconds=max(1.0, delay))

    def backoff_seconds(self, attempt: int, *, cap: float = 30.0) -> float:
        base = min(cap, 2 ** max(0, attempt))
        jitter = float(random.uniform(0, min(1.0, base * 0.2)))
        return float(base) + jitter

    def snapshot(self, now: datetime | None = None) -> ProviderCircuitState:
        return ProviderCircuitState(
            provider=self.provider,
            channel=self.channel,
            state=self.state,
            failure_count=self.failure_count,
            opened_at=self.opened_at,
            retry_after=self.retry_after,
            updated_at=now or datetime.now(tz=UTC),
            reason_codes=(f"PROVIDER_CIRCUIT_{self.state.value}",),
        )
