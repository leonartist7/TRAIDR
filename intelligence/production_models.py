"""Auditable contracts for live-public research, scoring, and replay."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataMode(str, Enum):
    FIXTURE = "fixture"
    PREVIEW = "preview"
    LIVE_PUBLIC = "live_public"
    REPLAY = "replay"


class MarketChannel(str, Enum):
    INSTRUMENT = "instrument"
    TICKER = "ticker"
    KLINE = "kline"
    DEPTH = "depth"
    TRADE = "trade"
    PRICE = "price"
    FUNDING = "funding"
    NEWS = "news"
    ONCHAIN = "onchain"


class EventQuality(str, Enum):
    SUFFICIENT = "sufficient"
    MISSING = "missing"
    STALE = "stale"
    MALFORMED = "malformed"
    CONTRADICTORY = "contradictory"
    UNCERTAIN = "uncertain"


class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


class ProbabilityState(str, Enum):
    CALIBRATED = "CALIBRATED"
    UNCALIBRATED = "UNCALIBRATED"
    BLOCKED = "BLOCKED"


class MappingReviewState(str, Enum):
    VERIFIED = "VERIFIED"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    REJECTED = "REJECTED"


class IngestionGapStatus(str, Enum):
    DETECTED = "DETECTED"
    BACKFILLING = "BACKFILLING"
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


class CircuitStatus(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ProductionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    can_execute_trades: Literal[False] = False


class CanonicalAssetIdentity(ProductionModel):
    canonical_asset_id: str
    symbol: str
    name: str
    aliases: tuple[str, ...]
    reviewed_at: datetime
    review_state: MappingReviewState = MappingReviewState.VERIFIED
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def _valid_identity(self) -> "CanonicalAssetIdentity":
        if not self.canonical_asset_id or not self.symbol or not self.aliases:
            raise ValueError("canonical asset identity requires stable identifiers and aliases")
        if self.reviewed_at.tzinfo is None or not self.reason_codes:
            raise ValueError("canonical asset identity requires reviewed provenance")
        return self


class SourceBinding(ProductionModel):
    binding_id: str
    canonical_asset_id: str
    source: str
    binding_kind: Literal["futures_symbol", "spot_id", "chain_asset", "contract", "dex_pair"]
    source_identifier: str
    chain_id: str | None = None
    contract_address: str | None = None
    review_state: MappingReviewState
    reviewed_at: datetime
    provenance: str
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def _exact_mapping_only(self) -> "SourceBinding":
        if not self.binding_id or not self.source_identifier or not self.provenance:
            raise ValueError("source binding requires exact reviewed provenance")
        if self.binding_kind in {"contract", "dex_pair"} and not self.chain_id:
            raise ValueError("chain-aware bindings require chain_id")
        if self.binding_kind == "contract" and not self.contract_address:
            raise ValueError("contract binding requires an address")
        return self


class EvidenceBundle(ProductionModel):
    bundle_id: str
    instrument_id: str
    canonical_asset_id: str | None
    observed_at: datetime
    generated_at: datetime
    feature_version: str
    technical: dict[str, Any]
    microstructure: dict[str, Any]
    futures_crowding: dict[str, Any]
    cross_market: dict[str, Any]
    news: tuple[dict[str, Any], ...] = ()
    onchain: dict[str, Any] = Field(default_factory=dict)
    data_coverage: float = Field(ge=0.0, le=1.0)
    missing_components: tuple[str, ...] = ()
    contradiction_flags: tuple[str, ...] = ()
    hard_vetoes: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


class IngestionGap(ProductionModel):
    gap_id: str
    idempotency_key: str
    source: str
    instrument_id: str
    channel: MarketChannel
    interval: str | None = None
    detected_at: datetime
    gap_start: datetime
    gap_end: datetime
    status: IngestionGapStatus
    attempts: int = 0
    updated_at: datetime
    reason_codes: tuple[str, ...]


class ProviderCircuitState(ProductionModel):
    provider: str
    channel: str
    state: CircuitStatus
    failure_count: int = 0
    opened_at: datetime | None = None
    retry_after: datetime | None = None
    updated_at: datetime
    reason_codes: tuple[str, ...]


class MarketEvent(ProductionModel):
    event_id: str
    idempotency_key: str
    data_mode: DataMode
    source: str
    instrument_id: str
    channel: MarketChannel
    event_at: datetime
    received_at: datetime
    sequence: int | None = None
    payload_version: str = "1"
    schema_fingerprint: str
    quality: EventQuality
    reason_codes: tuple[str, ...]
    payload: dict[str, Any]

    @model_validator(mode="after")
    def _valid_event(self) -> "MarketEvent":
        if not self.event_id or not self.idempotency_key or not self.schema_fingerprint:
            raise ValueError("market event identity is required")
        if self.event_at.tzinfo is None or self.received_at.tzinfo is None:
            raise ValueError("market event timestamps must be timezone-aware")
        if not self.reason_codes:
            raise ValueError("market event requires reason codes")
        return self

    def age_seconds(self, now: datetime | None = None) -> float:
        reference = now or datetime.now(tz=UTC)
        return max(0.0, (reference - self.event_at).total_seconds())


class DataHealth(ProductionModel):
    source: str
    instrument_id: str
    channel: MarketChannel
    status: Literal["HEALTHY", "DEGRADED", "DOWN"]
    checked_at: datetime
    last_event_at: datetime | None = None
    lag_seconds: float | None = None
    reconnect_count: int = 0
    gap_count: int = 0
    coverage: float = Field(ge=0.0, le=1.0)
    reason_codes: tuple[str, ...]


class FeatureSnapshot(ProductionModel):
    feature_id: str
    instrument_id: str
    horizon: Literal["5m", "15m", "1h", "4h", "1d"]
    observed_at: datetime
    calculated_at: datetime
    feature_version: str
    regime: str
    features: dict[str, float]
    data_coverage: float = Field(ge=0.0, le=1.0)
    missing_features: tuple[str, ...] = ()
    quality_warnings: tuple[str, ...] = ()
    contradiction_flags: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...]


class SignalDecision(ProductionModel):
    signal_id: str
    idempotency_key: str
    instrument_id: str
    direction: SignalDirection
    horizon: Literal["5m", "15m", "1h", "4h", "1d"]
    setup_type: str
    generated_at: datetime
    expires_at: datetime
    entry_low: Decimal | None = None
    entry_high: Decimal | None = None
    invalidation: Decimal | None = None
    stop: Decimal | None = None
    targets: tuple[Decimal, ...] = ()
    expected_return_pct: float | None = None
    risk_reward: float | None = None
    opportunity_score: float = Field(ge=0.0, le=100.0)
    risk_score: float = Field(ge=0.0, le=100.0)
    data_coverage: float = Field(ge=0.0, le=1.0)
    probability_state: ProbabilityState
    success_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    probability_low: float | None = Field(default=None, ge=0.0, le=1.0)
    probability_high: float | None = Field(default=None, ge=0.0, le=1.0)
    calibration_sample_size: int = 0
    model_version: str
    liquidity_grade: str
    risk_grade: str
    reasons: tuple[str, ...]
    hard_vetoes: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _valid_signal(self) -> "SignalDecision":
        if self.expires_at <= self.generated_at:
            raise ValueError("signal expiration must follow generation")
        if not self.reasons or not self.evidence_ids:
            raise ValueError("signal requires reasons and evidence")
        if self.probability_state is ProbabilityState.CALIBRATED:
            if self.success_probability is None or self.calibration_sample_size < 500:
                raise ValueError("calibrated probability requires at least 500 outcomes")
        elif any(value is not None for value in (self.success_probability, self.probability_low, self.probability_high)):
            raise ValueError("uncalibrated or blocked signals cannot carry probability percentages")
        if self.direction is SignalDirection.NO_TRADE:
            if any(value is not None for value in (self.entry_low, self.entry_high, self.stop)) or self.targets:
                raise ValueError("NO_TRADE cannot carry an actionable bracket")
        return self


class RiskAssessment(ProductionModel):
    assessment_id: str
    signal_id: str
    outcome: Literal["APPROVED_PAPER", "HOLD", "INSUFFICIENT_DATA"]
    decided_at: datetime
    approved_notional_usd: Decimal | None = None
    approved_leverage: Decimal | None = None
    reason_codes: tuple[str, ...]
    limit_checks: dict[str, bool]


class OutcomeLabel(ProductionModel):
    outcome_id: str
    signal_id: str
    evaluated_at: datetime
    target_before_stop: bool | None
    net_return_pct: float
    maximum_favorable_excursion_pct: float
    maximum_adverse_excursion_pct: float
    time_in_trade_seconds: int
    reason_codes: tuple[str, ...]


class BacktestRun(ProductionModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    strategy_version: str
    data_start: datetime
    data_end: datetime
    outcome_count: int
    metrics: dict[str, float]
    regime_metrics: dict[str, dict[str, float]] = Field(default_factory=dict)
    replay_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    no_lookahead_verified: bool


class CalibrationReport(ProductionModel):
    calibration_id: str
    direction: SignalDirection
    horizon: Literal["5m", "15m", "1h", "4h", "1d"]
    sample_size: int
    brier_score: float
    expected_calibration_error: float
    method: Literal["sigmoid", "isotonic", "none"]
    eligible_for_display: bool
    generated_at: datetime
    reason_codes: tuple[str, ...]


class ModelVersion(ProductionModel):
    model_id: str
    version: str
    role: Literal["baseline", "challenger", "champion"]
    feature_version: str
    training_start: datetime
    training_end: datetime
    metrics: dict[str, float]
    artifact_path: str
    active: bool


class ModelArtifactManifest(ProductionModel):
    artifact_id: str
    model_id: str
    version: str
    direction: SignalDirection
    horizon: Literal["5m", "15m", "1h", "4h", "1d"]
    role: Literal["baseline", "challenger", "champion"]
    feature_schema: tuple[str, ...]
    training_start: datetime
    training_end: datetime
    metrics: dict[str, float]
    artifact_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rollback_artifact_id: str | None = None
    active: bool
    created_at: datetime
    reason_codes: tuple[str, ...]


class CertificationReport(ProductionModel):
    certification_id: str
    started_at: datetime
    evaluated_at: datetime
    required_hours: int = 72
    elapsed_seconds: int = Field(ge=0)
    state: Literal["RUNNING", "PASSED", "FAILED", "INCOMPLETE"]
    paper_simulation_enabled: Literal[False] = False
    metrics: dict[str, float]
    gate_results: dict[str, bool]
    fault_results: dict[str, bool]
    replay_hashes: tuple[str, ...] = ()
    reason_codes: tuple[str, ...]
