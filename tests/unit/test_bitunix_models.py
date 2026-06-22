from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from data_pipeline.bitunix_models import (
    BitunixAdapterResult,
    BitunixDepthSnapshot,
    BitunixOrderBookLevel,
    BitunixTicker,
)


def test_bitunix_models_are_non_executing_and_forbid_extra_fields() -> None:
    ticker = BitunixTicker.model_validate(
        {
            "symbol": "BTCUSDT",
            "markPrice": "68000.1",
            "lastPrice": "68001.2",
            "open": "67000",
            "last": "68001.2",
            "quoteVol": "123456.78",
            "baseVol": "12.34",
            "high": "69000",
            "low": "66000",
            "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
    )

    assert ticker.can_execute_trades is False
    assert ticker.safe_dict()["can_execute_trades"] is False
    with pytest.raises(ValidationError):
        BitunixTicker.model_validate(
            {
                "symbol": "BTCUSDT",
                "markPrice": "68000.1",
                "lastPrice": "68001.2",
                "open": "67000",
                "last": "68001.2",
                "quoteVol": "123456.78",
                "baseVol": "12.34",
                "high": "69000",
                "low": "66000",
                "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
                "api_secret": "blocked",
            }
        )


def test_bitunix_depth_delta_math() -> None:
    depth = BitunixDepthSnapshot(
        symbol="HYPEUSDT",
        bids=(
            BitunixOrderBookLevel(price="67", amount="2"),
            BitunixOrderBookLevel(price="66.9", amount="4"),
        ),
        asks=(
            BitunixOrderBookLevel(price="67.1", amount="1"),
            BitunixOrderBookLevel(price="67.2", amount="1"),
        ),
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    delta = depth.depth_delta()

    assert delta.can_execute_trades is False
    assert delta.depth_delta_percent == 75


def test_bitunix_adapter_result_fails_closed_without_value() -> None:
    result = BitunixAdapterResult.insufficient("BITUNIX_HTTP_FAILED")

    assert result.status == "INSUFFICIENT_DATA"
    assert result.can_execute_trades is False
    assert result.value is None
