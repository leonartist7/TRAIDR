"""Chronological, cost-aware replay for labeling paper-only directional signals."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Sequence

from data_pipeline.bitunix_models import BitunixCandle
from intelligence.production_models import OutcomeLabel, SignalDecision, SignalDirection
from utils.results import Result


def replay_signal(
    signal: SignalDecision,
    candles: Sequence[BitunixCandle],
    *,
    fee_bps_round_trip: float = 12.0,
    slippage_bps_round_trip: float = 6.0,
    funding_pct: float = 0.0,
) -> Result[OutcomeLabel]:
    """Label a signal using only candles strictly after the decision timestamp."""

    if signal.direction is SignalDirection.NO_TRADE:
        return Result.insufficient_data("REPLAY_NO_TRADE_SIGNAL")
    if signal.stop is None or not signal.targets or signal.entry_low is None or signal.entry_high is None:
        return Result.insufficient_data("REPLAY_BRACKET_MISSING")
    eligible = [
        candle
        for candle in sorted(candles, key=lambda item: item.time_ms)
        if signal.generated_at < candle.observed_at <= signal.expires_at
    ]
    if not eligible:
        return Result.insufficient_data("REPLAY_FORWARD_CANDLES_MISSING")

    entry = (signal.entry_low + signal.entry_high) / Decimal("2")
    target = signal.targets[0]
    stop = signal.stop
    mfe = Decimal("0")
    mae = Decimal("0")
    exit_price = Decimal(str(eligible[-1].close))
    outcome: bool | None = None
    exit_time = eligible[-1].observed_at
    for candle in eligible:
        if signal.direction is SignalDirection.LONG:
            favorable = (candle.high - entry) / entry
            adverse = (entry - candle.low) / entry
            hit_stop = candle.low <= stop
            hit_target = candle.high >= target
        else:
            favorable = (entry - candle.low) / entry
            adverse = (candle.high - entry) / entry
            hit_stop = candle.high >= stop
            hit_target = candle.low <= target
        mfe = max(mfe, favorable)
        mae = max(mae, adverse)
        if hit_stop:
            outcome = False
            exit_price = stop
            exit_time = candle.observed_at
            break
        if hit_target:
            outcome = True
            exit_price = target
            exit_time = candle.observed_at
            break

    raw_return = (exit_price - entry) / entry
    if signal.direction is SignalDirection.SHORT:
        raw_return = -raw_return
    costs_pct = (fee_bps_round_trip + slippage_bps_round_trip) / 100.0 + funding_pct
    net_return_pct = float(raw_return * Decimal("100")) - costs_pct
    digest = sha256(
        f"{signal.signal_id}|{exit_time.isoformat()}|replay-v1".encode("utf-8")
    ).hexdigest()[:24]
    label = OutcomeLabel(
        outcome_id=f"outcome-{digest}",
        signal_id=signal.signal_id,
        evaluated_at=datetime.now(tz=UTC),
        target_before_stop=outcome,
        net_return_pct=round(net_return_pct, 8),
        maximum_favorable_excursion_pct=round(float(mfe * Decimal("100")), 8),
        maximum_adverse_excursion_pct=round(float(mae * Decimal("100")), 8),
        time_in_trade_seconds=max(0, int((exit_time - signal.generated_at).total_seconds())),
        reason_codes=("REPLAY_TARGET_OR_STOP" if outcome is not None else "REPLAY_EXPIRED", "COSTS_INCLUDED"),
    )
    return Result.success(label)


def chronological_walk_forward_splits(
    sample_count: int,
    *,
    minimum_train: int = 300,
    validation_size: int = 100,
    step: int = 100,
) -> tuple[tuple[range, range], ...]:
    if minimum_train < 1 or validation_size < 1 or step < 1:
        raise ValueError("walk-forward window sizes must be positive")
    splits: list[tuple[range, range]] = []
    train_end = minimum_train
    while train_end + validation_size <= sample_count:
        splits.append((range(0, train_end), range(train_end, train_end + validation_size)))
        train_end += step
    return tuple(splits)
