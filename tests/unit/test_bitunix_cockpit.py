from datetime import UTC, datetime

import dashboard.app
from dashboard.bitunix_cockpit import (
    CHART_ENGINE_PATH,
    _build_static_chart_html,
    build_chart_payload,
    build_preview_snapshot,
    insufficient_chart_payload,
)
from data_pipeline.bitunix_models import (
    BitunixCandle,
    BitunixCockpitSnapshot,
    BitunixDepthSnapshot,
    BitunixFundingRate,
    BitunixOrderBookLevel,
    BitunixTicker,
)


def test_bitunix_cockpit_chart_payload_is_non_executing() -> None:
    snapshot = _snapshot()

    payload = build_chart_payload(snapshot)

    assert payload["can_execute_trades"] is False
    assert len(payload["candles"]) == 4
    assert payload["overlays"]
    assert payload["support_resistance"]
    assert payload["risk_reward_boxes"]
    assert "order" not in str(payload).lower()
    assert "withdraw" not in str(payload).lower()


def test_bitunix_insufficient_chart_payload_fails_closed() -> None:
    payload = insufficient_chart_payload(["BITUNIX_HTTP_FAILED"])

    assert payload["can_execute_trades"] is False
    assert payload["candles"] == []
    assert "BITUNIX_HTTP_FAILED" in payload["reason_codes"]


def test_bitunix_preview_snapshot_renders_chart_before_live_fetch() -> None:
    snapshot = build_preview_snapshot("HYPEUSDT", "1h")
    payload = build_chart_payload(snapshot, data_mode="preview")

    assert snapshot.can_execute_trades is False
    assert payload["can_execute_trades"] is False
    assert payload["data_mode"] == "preview"
    assert payload["candles"]
    assert "REFRESH_FOR_LIVE_BITUNIX" in payload["reason_codes"]


def test_bitunix_chart_engine_asset_exists_and_has_no_order_controls() -> None:
    engine = CHART_ENGINE_PATH.read_text(encoding="utf-8")

    assert "renderTRAIDRBitunixChart" in engine
    assert "INSUFFICIENT_DATA" in engine
    assert "Open Long" not in engine
    assert "Open Short" not in engine
    assert dashboard.app is not None


def test_bitunix_static_chart_html_contains_visible_svg_candles() -> None:
    payload = build_chart_payload(_snapshot())

    html = _build_static_chart_html(payload)

    assert "traidr-candlestick-chart" in html
    assert "<svg" in html
    assert "<rect" in html
    assert "can_execute_trades: false" in html
    assert "Open Long" not in html
    assert "Open Short" not in html


def test_bitunix_static_chart_html_fails_closed_without_candles() -> None:
    html = _build_static_chart_html(insufficient_chart_payload(["BITUNIX_HTTP_FAILED"]))

    assert "INSUFFICIENT_DATA" in html
    assert "can_execute_trades: false" in html


def _snapshot() -> BitunixCockpitSnapshot:
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    candles = tuple(
        BitunixCandle(
            symbol="BTCUSDT",
            interval="1h",
            time=str(int(now.timestamp() * 1000) - (3 - index) * 3_600_000),
            open=str(100 + index),
            high=str(103 + index),
            low=str(99 + index),
            close=str(101 + index),
            quoteVol="1000",
            baseVol="10",
            type="LAST_PRICE",
        )
        for index in range(4)
    )
    depth = BitunixDepthSnapshot(
        symbol="BTCUSDT",
        bids=(BitunixOrderBookLevel(price="103", amount="5"),),
        asks=(BitunixOrderBookLevel(price="104", amount="5"),),
        observed_at=now,
    )
    return BitunixCockpitSnapshot(
        symbol="BTCUSDT",
        interval="1h",
        ticker=BitunixTicker(
            symbol="BTCUSDT",
            markPrice="103",
            lastPrice="103",
            open="100",
            last="103",
            quoteVol="1000000",
            baseVol="10000",
            high="105",
            low="99",
            observed_at=now,
        ),
        candles=candles,
        funding_rate=BitunixFundingRate(
            symbol="BTCUSDT",
            markPrice="103",
            lastPrice="103",
            fundingRate="0.0001",
            fundingInterval=8,
            nextFundingTime=str(int(now.timestamp() * 1000) + 3_600_000),
            maxFundingRate="0.003",
            minFundingRate="-0.003",
            observed_at=now,
        ),
        depth=depth,
        depth_delta=depth.depth_delta(),
        opportunity_rating=70,
        risk_rating=25,
        reason_codes=("BITUNIX_COCKPIT_OK", "NO_EXECUTION_ACTION"),
        observed_at=now,
    )
