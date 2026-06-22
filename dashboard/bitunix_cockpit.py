"""Bitunix read-only futures cockpit for the Streamlit dashboard."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from data_pipeline.bitunix_futures_adapter import BitunixFuturesAdapter
from data_pipeline.bitunix_models import (
    BITUNIX_ALLOWED_DEPTH_LIMITS,
    BITUNIX_ALLOWED_INTERVALS,
    BITUNIX_ALLOWED_SYMBOLS,
    BitunixAdapterResult,
    BitunixCandle,
    BitunixCockpitSnapshot,
    BitunixDepthSnapshot,
    BitunixFundingRate,
    BitunixOrderBookLevel,
    BitunixTicker,
)
from storage.duckdb_store import DuckDBStore
from storage.repositories import ResearchRepository
from storage.schema import initialize_schema

CHART_ENGINE_PATH = Path(__file__).resolve().parent / "components" / "chart_engine.js"


def render(database_path: str | Path) -> None:
    """Render the research-only Bitunix futures cockpit."""

    st.header("Bitunix Futures")
    st.caption("Coin chart first. Public Bitunix futures data only. No orders, no private keys, no exchange execution.")

    control_columns = st.columns([1, 1, 1, 1])
    symbol = control_columns[0].selectbox("Pair", BITUNIX_ALLOWED_SYMBOLS, index=0)
    interval = control_columns[1].selectbox("Interval", BITUNIX_ALLOWED_INTERVALS, index=3)
    depth_limit = control_columns[2].selectbox("Depth", BITUNIX_ALLOWED_DEPTH_LIMITS, index=2)
    persist = control_columns[3].checkbox("Persist read-only evidence", value=True)

    session_key = f"bitunix:{symbol}:{interval}:{depth_limit}"
    if st.button("Refresh Real Bitunix Data", type="primary", use_container_width=True):
        with st.spinner("Fetching public Bitunix futures data..."):
            result = _run_async(BitunixFuturesAdapter().fetch_cockpit_snapshot(symbol, interval, depth_limit))
        st.session_state[session_key] = result
        if result.ok and persist and isinstance(result.value, BitunixCockpitSnapshot):
            snapshot_id = persist_cockpit_snapshot(database_path, result.value)
            st.success(f"Read-only Bitunix evidence saved: {snapshot_id}")
        elif result.ok:
            st.success("Read-only Bitunix data loaded.")
        else:
            st.error("Bitunix data is insufficient. No bullish data was fabricated.")

    result = st.session_state.get(session_key)
    if result is None:
        snapshot = build_preview_snapshot(symbol, interval)
        st.info("Preview chart shown. Press Refresh Real Bitunix Data to replace it with public Bitunix data.")
        _render_readouts(snapshot, label="Preview data")
        render_chart(build_chart_payload(snapshot, data_mode="preview"))
        return
    if not isinstance(result, BitunixAdapterResult) or not result.ok or not isinstance(result.value, BitunixCockpitSnapshot):
        reason_codes = list(getattr(result, "reason_codes", ("BITUNIX_INSUFFICIENT_DATA",)))
        _render_insufficient(reason_codes)
        st.info("Real data is unavailable right now, so TRAIDR is showing a clearly marked preview chart instead of fake live data.")
        render_chart(build_chart_payload(build_preview_snapshot(symbol, interval), data_mode="preview"))
        return

    snapshot = result.value
    _render_readouts(snapshot, label="Live public Bitunix data")
    render_chart(build_chart_payload(snapshot, data_mode="live_public_bitunix"))


def build_chart_payload(snapshot: BitunixCockpitSnapshot, *, data_mode: str = "live_public_bitunix") -> dict[str, Any]:
    """Build the chart payload consumed by chart_engine.js."""

    candles = snapshot.chart_candles()
    support_resistance = _support_resistance(snapshot.candles)
    overlays = _trend_overlays(snapshot.candles)
    fvg_zones = _fair_value_gaps(snapshot.candles)
    risk_reward_boxes = _risk_reward_boxes(snapshot.candles)
    return {
        "symbol": snapshot.symbol,
        "interval": snapshot.interval,
        "candles": candles,
        "overlays": overlays,
        "fvg_zones": fvg_zones,
        "risk_reward_boxes": risk_reward_boxes,
        "support_resistance": support_resistance,
        "metrics": {
            "data_mode": data_mode,
            "last_price": float(snapshot.ticker.last_price),
            "high_24h": float(snapshot.ticker.high),
            "low_24h": float(snapshot.ticker.low),
            "quote_volume_24h": float(snapshot.ticker.quote_volume),
            "funding_rate": float(snapshot.funding_rate.funding_rate),
            "next_funding_at": snapshot.funding_rate.next_funding_at.isoformat(),
            "depth_delta_percent": float(snapshot.depth_delta.depth_delta_percent),
            "opportunity_rating": snapshot.opportunity_rating,
            "risk_rating": snapshot.risk_rating,
        },
        "reason_codes": list(snapshot.reason_codes),
        "data_mode": data_mode,
        "can_execute_trades": False,
    }


def build_preview_snapshot(symbol: str = "HYPEUSDT", interval: str = "1h") -> BitunixCockpitSnapshot:
    """Build a clearly labeled preview chart so the cockpit never opens blank."""

    now = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    base = 68.0 if symbol == "HYPEUSDT" else 102000.0
    step = 0.42 if symbol == "HYPEUSDT" else 420.0
    pattern = (0, 1.2, -0.4, 1.7, 0.8, 2.0, 1.1, 2.8, 2.2, 3.4, 2.6, 4.1, 3.1, 4.7, 3.9, 5.2)
    interval_seconds = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}.get(interval, 3600)
    candles: list[BitunixCandle] = []
    for index, offset in enumerate(pattern):
        open_price = base + (offset * step)
        close_price = open_price + ((0.7 if index % 2 == 0 else -0.35) * step)
        high = max(open_price, close_price) + (0.9 * step)
        low = min(open_price, close_price) - (0.8 * step)
        candles.append(
            BitunixCandle(
                symbol=symbol,
                interval=interval,
                time=str(int((now.timestamp() - (len(pattern) - index) * interval_seconds) * 1000)),
                open=str(round(open_price, 8)),
                high=str(round(high, 8)),
                low=str(round(low, 8)),
                close=str(round(close_price, 8)),
                quoteVol=str(10000 + index * 600),
                baseVol=str(120 + index * 4),
                type="LAST_PRICE",
            )
        )
    last = candles[-1].close
    high_24h = max(candle.high for candle in candles)
    low_24h = min(candle.low for candle in candles)
    depth = BitunixDepthSnapshot(
        symbol=symbol,
        bids=(BitunixOrderBookLevel(price=str(last), amount="6"),),
        asks=(BitunixOrderBookLevel(price=str(last + (last * Decimal("0.001"))), amount="4"),),
        observed_at=now,
    )
    return BitunixCockpitSnapshot(
        symbol=symbol,
        interval=interval,
        ticker=BitunixTicker(
            symbol=symbol,
            markPrice=str(last),
            lastPrice=str(last),
            open=str(candles[0].open),
            last=str(last),
            quoteVol="2500000",
            baseVol="35000",
            high=str(high_24h),
            low=str(low_24h),
            observed_at=now,
        ),
        candles=tuple(candles),
        funding_rate=BitunixFundingRate(
            symbol=symbol,
            markPrice=str(last),
            lastPrice=str(last),
            fundingRate="0.0001",
            fundingInterval=8,
            nextFundingTime=str(int((now.timestamp() + 8 * 3600) * 1000)),
            maxFundingRate="0.003",
            minFundingRate="-0.003",
            observed_at=now,
        ),
        depth=depth,
        depth_delta=depth.depth_delta(),
        opportunity_rating=64,
        risk_rating=30,
        reason_codes=("PREVIEW_DATA", "REFRESH_FOR_LIVE_BITUNIX", "NO_EXECUTION_ACTION"),
        observed_at=now,
    )


def insufficient_chart_payload(reason_codes: list[str] | tuple[str, ...]) -> dict[str, Any]:
    return {
        "candles": [],
        "overlays": [],
        "fvg_zones": [],
        "risk_reward_boxes": [],
        "support_resistance": [],
        "reason": ", ".join(reason_codes),
        "reason_codes": list(reason_codes),
        "can_execute_trades": False,
    }


def persist_cockpit_snapshot(database_path: str | Path, snapshot: BitunixCockpitSnapshot) -> str:
    path = Path(database_path)
    if path != Path(":memory:") and path.parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    with DuckDBStore(path) as store:
        initialize_schema(store.connection)
        repository = ResearchRepository(store.connection)
        return repository.record_evidence(
            source_name=f"bitunix_futures:{snapshot.symbol}:{snapshot.interval}",
            observed_at=snapshot.observed_at,
            quality_status="sufficient",
            payload=build_chart_payload(snapshot),
            provenance={
                "source": "bitunix",
                "source_url": "https://fapi.bitunix.com",
                "symbol": snapshot.symbol,
                "interval": snapshot.interval,
                "retrieved_at": datetime.now(tz=UTC).isoformat(),
                "can_execute_trades": False,
            },
            collected_at=datetime.now(tz=UTC),
        )


def render_chart(payload: dict[str, Any]) -> None:
    container_id = f"traidr-bitunix-chart-{abs(hash(json.dumps(payload, sort_keys=True))) % 10_000_000}"
    engine = CHART_ENGINE_PATH.read_text(encoding="utf-8")
    html = f"""
    <div id="{container_id}"></div>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script>{engine}</script>
    <script>
      window.renderTRAIDRBitunixChart({json.dumps(container_id)}, {json.dumps(payload)});
    </script>
    """
    components.html(html, height=660, scrolling=False)


def _render_readouts(snapshot: BitunixCockpitSnapshot, *, label: str) -> None:
    st.subheader(f"{snapshot.symbol} · {snapshot.interval} · {label}")
    metrics = st.columns(5)
    metrics[0].metric("Last", f"{float(snapshot.ticker.last_price):,.4f}")
    metrics[1].metric("24h High", f"{float(snapshot.ticker.high):,.4f}")
    metrics[2].metric("24h Low", f"{float(snapshot.ticker.low):,.4f}")
    metrics[3].metric("Depth Delta", f"{float(snapshot.depth_delta.depth_delta_percent):.2f}%")
    metrics[4].metric("Funding", f"{float(snapshot.funding_rate.funding_rate):.5f}")

    score_columns = st.columns(3)
    score_columns[0].metric("Opportunity Rating", snapshot.opportunity_rating)
    score_columns[1].metric("Safety Risk", snapshot.risk_rating)
    score_columns[2].metric("Can Execute Trades", "false")
    st.write("Reason codes:", ", ".join(snapshot.reason_codes))


def _render_insufficient(reason_codes: list[str]) -> None:
    st.subheader("INSUFFICIENT_DATA")
    st.write("Reason codes:", ", ".join(reason_codes))
    st.write("can_execute_trades: false")


def _support_resistance(candles: tuple[BitunixCandle, ...]) -> list[dict[str, Any]]:
    recent = candles[-80:] if len(candles) > 80 else candles
    high = max(float(candle.high) for candle in recent)
    low = min(float(candle.low) for candle in recent)
    return [
        {"price": high, "label": "Resistance", "color": "#f97316"},
        {"price": low, "label": "Support", "color": "#22c55e"},
    ]


def _trend_overlays(candles: tuple[BitunixCandle, ...]) -> list[dict[str, Any]]:
    if len(candles) < 2:
        return []
    start = candles[0]
    end = candles[-1]
    return [
        {
            "kind": "trendline",
            "label": "BoS vector",
            "start_time": int(start.time_ms / 1000),
            "end_time": int(end.time_ms / 1000),
            "start_price": float(start.close),
            "end_price": float(end.close),
            "color": "#22d3ee",
        }
    ]


def _fair_value_gaps(candles: tuple[BitunixCandle, ...]) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    for index in range(2, len(candles)):
        left = candles[index - 2]
        current = candles[index]
        if current.low > left.high:
            zones.append(
                {
                    "label": "Bullish FVG",
                    "start_time": int(left.time_ms / 1000),
                    "end_time": int(current.time_ms / 1000),
                    "high": float(current.low),
                    "low": float(left.high),
                }
            )
        elif current.high < left.low:
            zones.append(
                {
                    "label": "Bearish FVG",
                    "start_time": int(left.time_ms / 1000),
                    "end_time": int(current.time_ms / 1000),
                    "high": float(left.low),
                    "low": float(current.high),
                }
            )
    return zones[-8:]


def _risk_reward_boxes(candles: tuple[BitunixCandle, ...]) -> list[dict[str, Any]]:
    if len(candles) < 2:
        return []
    recent = candles[-14:] if len(candles) >= 14 else candles
    entry = float(candles[-1].close)
    high = max(float(candle.high) for candle in recent)
    low = min(float(candle.low) for candle in recent)
    span = max(high - low, entry * 0.005)
    end_time = int(candles[-1].time_ms / 1000)
    start_time = int(candles[max(0, len(candles) - 12)].time_ms / 1000)
    return [
        {
            "label": "Research bracket",
            "start_time": start_time,
            "end_time": end_time,
            "entry": entry,
            "target": entry + span,
            "stop": max(0.00000001, entry - span * 0.5),
        }
    ]


def _run_async(awaitable: Any) -> Any:
    return asyncio.run(awaitable)
