"""Unified, read-only market-provider contracts and deterministic source merging."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from statistics import median
from typing import Any, Generic, Protocol, TypeVar


class ProviderCapability(StrEnum):
    CANDLES = "candles"
    ORDER_BOOK = "order_book"
    TRADES = "trades"
    TICKERS = "tickers"
    FUNDING = "funding"
    OPEN_INTEREST = "open_interest"
    LIQUIDATIONS = "liquidations"
    LONG_SHORT = "long_short"
    MARKET_DATA = "market_data"
    METADATA = "metadata"
    NEWS = "news"
    EVENTS = "events"


class ProviderHealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ProviderHttpResponse:
    status_code: int
    payload: Mapping[str, Any] | list[Any] | None
    headers: Mapping[str, str] = field(default_factory=dict)
    received_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass(frozen=True)
class ProviderObservation:
    provider: str
    instrument_id: str
    observed_at: datetime
    received_at: datetime
    fields: Mapping[str, float]
    capabilities: tuple[ProviderCapability, ...]
    metadata: Mapping[str, str] = field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
    can_execute_trades: bool = False


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    checked_at: datetime
    status: ProviderHealthStatus
    latency_ms: float | None
    clock_skew_ms: float | None
    consecutive_failures: int
    rate_limited: bool
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False


T = TypeVar("T")


@dataclass(frozen=True)
class ProviderResult(Generic[T]):
    provider: str
    status: ProviderHealthStatus
    value: T | None
    health: ProviderHealth
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    @property
    def ok(self) -> bool:
        return self.status is ProviderHealthStatus.HEALTHY and self.value is not None

    @classmethod
    def insufficient(
        cls,
        provider: str,
        health: ProviderHealth,
        *reason_codes: str,
    ) -> "ProviderResult[T]":
        return cls(
            provider=provider,
            status=ProviderHealthStatus.INSUFFICIENT_DATA,
            value=None,
            health=health,
            reason_codes=tuple(reason_codes) or ("PROVIDER_INSUFFICIENT_DATA",),
        )


ProviderTransport = Callable[
    [str, Mapping[str, str], Mapping[str, str]],
    ProviderHttpResponse | Awaitable[ProviderHttpResponse],
]


class ReadOnlyMarketProvider(Protocol):
    name: str
    capabilities: tuple[ProviderCapability, ...]

    async def fetch(
        self,
        instrument_id: str,
        *,
        now: datetime | None = None,
    ) -> ProviderResult[ProviderObservation]:
        ...

    async def health_check(self, *, now: datetime | None = None) -> ProviderHealth:
        ...


@dataclass(frozen=True)
class SourceConflict:
    instrument_id: str
    field: str
    values: Mapping[str, float]
    relative_difference: float
    critical: bool
    reason_code: str = "SOURCE_CONFLICT"


DEFAULT_MAX_OBSERVATION_AGE = timedelta(minutes=5)


@dataclass(frozen=True)
class MarketDataBundle:
    instrument_id: str
    observed_at: datetime | None
    fields: Mapping[str, float]
    field_sources: Mapping[str, str]
    observations: tuple[ProviderObservation, ...]
    conflicts: tuple[SourceConflict, ...]
    health: tuple[ProviderHealth, ...]
    status: ProviderHealthStatus
    reason_codes: tuple[str, ...]
    observation_ages_seconds: Mapping[str, float] = field(default_factory=dict)
    stale_observation_ages_seconds: Mapping[str, float] = field(default_factory=dict)
    maximum_observation_age_seconds: float = DEFAULT_MAX_OBSERVATION_AGE.total_seconds()
    can_execute_trades: bool = False

    @property
    def has_critical_conflict(self) -> bool:
        return any(conflict.critical for conflict in self.conflicts)


DEFAULT_CONFLICT_THRESHOLDS: Mapping[str, float] = {
    "price_usd": 0.01,
    "mark_price": 0.01,
    "index_price": 0.01,
    "funding_rate": 0.001,
    "open_interest": 0.10,
    "oi_change_pct": 0.15,
    "volume_24h_usd": 0.25,
    "market_cap": 0.15,
    "long_short_ratio": 0.15,
    "liquidation_pressure": 0.25,
    "risk_reward": 0.20,
}

DEFAULT_CRITICAL_FIELDS = frozenset(
    {
        "price_usd",
        "mark_price",
        "index_price",
        "funding_rate",
        "open_interest",
        "oi_change_pct",
    }
)


def normalize_timestamp(
    value: Any,
    *,
    received_at: datetime | None = None,
    maximum_future_skew: timedelta = timedelta(minutes=2),
) -> datetime | None:
    """Normalize provider timestamps to UTC and reject implausible future values."""

    reference = (received_at or datetime.now(tz=UTC)).astimezone(UTC)
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 10_000_000_000:
            numeric /= 1000.0
        if numeric > 0:
            parsed = datetime.fromtimestamp(numeric, tz=UTC)
    elif isinstance(value, str) and value.strip():
        candidate = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            try:
                numeric = float(candidate)
            except ValueError:
                parsed = None
            else:
                if numeric > 10_000_000_000:
                    numeric /= 1000.0
                if numeric > 0:
                    parsed = datetime.fromtimestamp(numeric, tz=UTC)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    normalized = parsed.astimezone(UTC)
    if normalized - reference > maximum_future_skew:
        return None
    return normalized


class TTLCache(Generic[T]):
    """Small in-process cache; it never persists secrets or provider payloads."""

    def __init__(self, ttl_seconds: float = 15.0) -> None:
        if ttl_seconds <= 0:
            raise ValueError("cache TTL must be positive")
        self.ttl = timedelta(seconds=ttl_seconds)
        self._entries: dict[str, tuple[datetime, T]] = {}

    def get(self, key: str, *, now: datetime | None = None) -> T | None:
        reference = (now or datetime.now(tz=UTC)).astimezone(UTC)
        entry = self._entries.get(key)
        if entry is None:
            return None
        cached_at, value = entry
        if reference - cached_at > self.ttl:
            self._entries.pop(key, None)
            return None
        return value

    def set(self, key: str, value: T, *, now: datetime | None = None) -> None:
        reference = (now or datetime.now(tz=UTC)).astimezone(UTC)
        self._entries[key] = (reference, value)

    def clear(self) -> None:
        self._entries.clear()


def merge_provider_observations(
    instrument_id: str,
    results: Sequence[ProviderResult[ProviderObservation]],
    *,
    now: datetime | None = None,
    source_preference: Sequence[str] = ("bitunix_public", "coinglass", "coingecko", "coinmarketcap"),
    conflict_thresholds: Mapping[str, float] = DEFAULT_CONFLICT_THRESHOLDS,
    critical_fields: frozenset[str] = DEFAULT_CRITICAL_FIELDS,
    maximum_observation_age: timedelta = DEFAULT_MAX_OBSERVATION_AGE,
) -> MarketDataBundle:
    """Merge healthy observations without hiding disagreements between providers."""

    if maximum_observation_age <= timedelta(0):
        raise ValueError("maximum observation age must be positive")
    reference = (now or datetime.now(tz=UTC)).astimezone(UTC)
    accepted_observations: list[ProviderObservation] = []
    observation_ages: dict[str, float] = {}
    stale_observation_ages: dict[str, float] = {}
    health = tuple(result.health for result in results)
    reasons: list[str] = []
    for result in results:
        reasons.extend(result.reason_codes)
        if not result.ok or result.value is None:
            continue
        observed_at = _as_utc_datetime(result.value.observed_at)
        age = reference - observed_at
        age_seconds = age.total_seconds()
        if age > maximum_observation_age:
            stale_observation_ages[result.provider] = age_seconds
            reasons.extend(
                (
                    "STALE_PROVIDER_OBSERVATION",
                    f"STALE_PROVIDER_{result.provider.upper().replace('-', '_')}"
                )
            )
            continue
        if age < timedelta(0):
            stale_observation_ages[result.provider] = age_seconds
            reasons.extend(
                (
                    "FUTURE_PROVIDER_OBSERVATION",
                    f"FUTURE_PROVIDER_{result.provider.upper().replace('-', '_')}"
                )
            )
            continue
        accepted_observations.append(result.value)
        observation_ages[result.provider] = age_seconds
    observations = tuple(accepted_observations)
    if not observations:
        return MarketDataBundle(
            instrument_id=instrument_id,
            observed_at=None,
            fields={},
            field_sources={},
            observations=(),
            conflicts=(),
            health=health,
            status=ProviderHealthStatus.INSUFFICIENT_DATA,
            reason_codes=tuple(
                dict.fromkeys((*reasons, "NO_FRESH_PROVIDER_OBSERVATION", "NO_HEALTHY_PROVIDER_OBSERVATION"))
            ),
            observation_ages_seconds=observation_ages,
            stale_observation_ages_seconds=stale_observation_ages,
            maximum_observation_age_seconds=maximum_observation_age.total_seconds(),
        )

    values_by_field: dict[str, list[tuple[str, float]]] = {}
    for observation in observations:
        for field_name, value in observation.fields.items():
            values_by_field.setdefault(field_name, []).append((observation.provider, float(value)))

    fields: dict[str, float] = {}
    field_sources: dict[str, str] = {}
    conflicts: list[SourceConflict] = []
    preference = {name: index for index, name in enumerate(source_preference)}

    for field_name, values in values_by_field.items():
        finite = [(source, value) for source, value in values if value == value and abs(value) != float("inf")]
        if not finite:
            continue
        source_values = {source: value for source, value in finite}
        low = min(value for _, value in finite)
        high = max(value for _, value in finite)
        scale = max(abs(median([value for _, value in finite])), 1e-12)
        relative_difference = abs(high - low) / scale
        threshold = conflict_thresholds.get(field_name, 0.20)
        if len(finite) > 1 and relative_difference > threshold:
            critical = field_name in critical_fields
            conflicts.append(
                SourceConflict(
                    instrument_id=instrument_id,
                    field=field_name,
                    values=source_values,
                    relative_difference=relative_difference,
                    critical=critical,
                )
            )
        chosen_source, chosen_value = min(
            finite,
            key=lambda item: (preference.get(item[0], len(preference)), item[0]),
        )
        fields[field_name] = chosen_value
        field_sources[field_name] = chosen_source

    latest = max((_as_utc_datetime(observation.observed_at) for observation in observations), default=None)
    if conflicts:
        reasons.append("SOURCE_CONFLICT_WARNING")
    if any(conflict.critical for conflict in conflicts):
        reasons.append("CRITICAL_SOURCE_CONFLICT")
    status = (
        ProviderHealthStatus.DEGRADED
        if conflicts or stale_observation_ages
        else ProviderHealthStatus.HEALTHY
    )
    return MarketDataBundle(
        instrument_id=instrument_id,
        observed_at=latest,
        fields=fields,
        field_sources=field_sources,
        observations=observations,
        conflicts=tuple(conflicts),
        health=health,
        status=status,
        reason_codes=tuple(dict.fromkeys(reasons or ["PROVIDERS_MERGED"])),
        observation_ages_seconds=observation_ages,
        stale_observation_ages_seconds=stale_observation_ages,
        maximum_observation_age_seconds=maximum_observation_age.total_seconds(),
    )


def _as_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
