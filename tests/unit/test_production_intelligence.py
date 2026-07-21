from datetime import UTC, datetime, timedelta
from decimal import Decimal

from data_pipeline.bitunix_models import BitunixCandle
from intelligence.production_models import ProbabilityState, SignalDirection
from scoring.calibration import ProbabilityEvidence, expected_calibration_error
from scoring.signal_engine import score_directional_setup
from technicals.multi_horizon import build_multi_horizon_features


NOW = datetime(2026, 7, 20, 12, tzinfo=UTC)


def test_multi_horizon_signal_is_directional_but_probability_is_gated() -> None:
    feature_result = build_multi_horizon_features(
        instrument_id="bitunix:BTCUSDT",
        horizon="5m",
        candles=_trend_candles(up=True),
        evidence_ids=("evidence-live-btc",),
        depth_imbalance=0.25,
        spread_bps=2.0,
        funding_rate=0.0001,
        basis_bps=1.0,
        now=NOW,
    )

    assert feature_result.ok
    assert feature_result.value is not None
    uncalibrated = score_directional_setup(feature_result.value)
    calibrated = score_directional_setup(
        feature_result.value,
        probability_evidence=ProbabilityEvidence(0.72, 600, 0.04, "walk-forward-v1"),
    )

    assert uncalibrated.direction is SignalDirection.LONG
    assert uncalibrated.probability_state is ProbabilityState.UNCALIBRATED
    assert uncalibrated.success_probability is None
    assert calibrated.probability_state is ProbabilityState.CALIBRATED
    assert calibrated.success_probability == 0.72
    assert calibrated.calibration_sample_size == 600
    assert calibrated.can_execute_trades is False


def test_missing_coverage_or_token_safety_forces_no_trade() -> None:
    feature_result = build_multi_horizon_features(
        instrument_id="bitunix:MICROUSDT",
        horizon="5m",
        candles=_trend_candles(up=True, symbol="MICROUSDT"),
        evidence_ids=("evidence-micro",),
        now=NOW,
    )

    assert feature_result.ok and feature_result.value is not None
    signal = score_directional_setup(
        feature_result.value,
        token_safety_required=True,
        token_safety_clear=None,
    )

    assert signal.direction is SignalDirection.NO_TRADE
    assert "DATA_COVERAGE_INSUFFICIENT" in signal.hard_vetoes
    assert "TOKEN_SAFETY_NOT_VERIFIED" in signal.hard_vetoes
    assert signal.targets == ()
    assert signal.probability_state is ProbabilityState.BLOCKED


def test_calibration_error_matches_perfect_bins() -> None:
    error = expected_calibration_error([0.0, 0.0, 1.0, 1.0], [0, 0, 1, 1])
    assert error == 0.0


def _trend_candles(*, up: bool, symbol: str = "BTCUSDT") -> tuple[BitunixCandle, ...]:
    rows = []
    for index in range(60):
        offset = index if up else -index
        close = Decimal("100") + Decimal(offset) * Decimal("0.5")
        open_price = close - Decimal("0.15") if up else close + Decimal("0.15")
        rows.append(
            BitunixCandle(
                symbol=symbol,
                interval="5m",
                time=int((NOW - timedelta(minutes=(59 - index) * 5)).timestamp() * 1000),
                open=open_price,
                high=max(open_price, close) + Decimal("0.25"),
                low=min(open_price, close) - Decimal("0.25"),
                close=close,
                quoteVol=Decimal("100000") + index * 100,
                baseVol=Decimal("1000") + index * 5,
            )
        )
    return tuple(rows)
