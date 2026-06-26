"""Bitunix read-only futures cockpit for the Streamlit dashboard."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

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

    st.markdown(
        """
        <div class="traidr-panel">
          <h3>Bitunix Futures</h3>
          <p>Native public-data chart. No iframe, no order controls, no API keys, no exchange execution.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
        _render_cockpit(snapshot, data_mode="preview", status_label="Preview data")
        return
    if not isinstance(result, BitunixAdapterResult) or not result.ok or not isinstance(result.value, BitunixCockpitSnapshot):
        reason_codes = list(getattr(result, "reason_codes", ("BITUNIX_INSUFFICIENT_DATA",)))
        _render_insufficient(reason_codes)
        st.info("Real data is unavailable right now, so TRAIDR is showing a clearly marked preview chart instead of fake live data.")
        _render_cockpit(
            build_preview_snapshot(symbol, interval),
            data_mode="preview",
            status_label="Fail-closed preview",
        )
        return

    snapshot = result.value
    _render_cockpit(snapshot, data_mode="live_public_bitunix", status_label="Live public Bitunix data")


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
    """Render a visible chart without relying on external JS/CDN loading."""

    st.markdown(_build_static_chart_html(payload), unsafe_allow_html=True)


def _build_static_chart_html(payload: dict[str, Any]) -> str:
    """Build a deterministic native SVG candlestick chart for Streamlit."""

    candles = payload.get("candles")
    if payload.get("can_execute_trades") is not False or not isinstance(candles, list) or not candles:
        reason = escape(str(payload.get("reason") or "No chartable candles were provided."))
        return f"""
        <div class="traidr-static-chart traidr-static-chart-empty">
          <h3>INSUFFICIENT_DATA</h3>
          <p>{reason}</p>
          <p>can_execute_trades: false</p>
        </div>
        """

    width = 1120
    height = 620
    left = 64
    right = 74
    top = 34
    bottom = 58
    chart_w = width - left - right
    chart_h = height - top - bottom
    highs = [float(candle["high"]) for candle in candles]
    lows = [float(candle["low"]) for candle in candles]
    prices = highs + lows
    for level in payload.get("support_resistance", []):
        prices.append(float(level["price"]))
    for box in payload.get("risk_reward_boxes", []):
        prices.extend([float(box["entry"]), float(box["target"]), float(box["stop"])])
    min_price = min(prices)
    max_price = max(prices)
    span = max(max_price - min_price, max_price * 0.01)
    min_price -= span * 0.08
    max_price += span * 0.08
    total_span = max_price - min_price
    candle_count = len(candles)
    spacing = chart_w / max(candle_count - 1, 1)
    body_width = max(4, min(14, spacing * 0.52))
    by_time = {int(candle["time"]): index for index, candle in enumerate(candles)}

    def x_for_index(index: int) -> float:
        return left + index * spacing

    def x_for_time(timestamp: Any) -> float:
        numeric = int(timestamp)
        if numeric in by_time:
            return x_for_index(by_time[numeric])
        times = sorted(by_time)
        if not times:
            return left
        if numeric <= times[0]:
            return left
        if numeric >= times[-1]:
            return left + chart_w
        for pos, current in enumerate(times[1:], start=1):
            previous = times[pos - 1]
            if previous <= numeric <= current:
                ratio = (numeric - previous) / max(current - previous, 1)
                return x_for_index(pos - 1) + ratio * spacing
        return left

    def y_for_price(price: Any) -> float:
        return top + ((max_price - float(price)) / total_span) * chart_h

    grid = []
    labels = []
    for index in range(6):
        y = top + (chart_h / 5) * index
        price = max_price - (total_span / 5) * index
        grid.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + chart_w}" y2="{y:.2f}" stroke="#17202b" stroke-width="1" />')
        labels.append(f'<text x="{left + chart_w + 12}" y="{y + 4:.2f}" fill="#9da8b7" font-size="12">{price:.4f}</text>')
    for index in range(0, candle_count, max(1, candle_count // 8)):
        x = x_for_index(index)
        grid.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + chart_h}" stroke="#111923" stroke-width="1" />')

    candle_shapes = []
    for index, candle in enumerate(candles):
        x = x_for_index(index)
        open_y = y_for_price(candle["open"])
        close_y = y_for_price(candle["close"])
        high_y = y_for_price(candle["high"])
        low_y = y_for_price(candle["low"])
        is_up = float(candle["close"]) >= float(candle["open"])
        color = "#00c084" if is_up else "#ff4d4f"
        body_top = min(open_y, close_y)
        body_h = max(abs(close_y - open_y), 2)
        candle_shapes.append(f'<line x1="{x:.2f}" y1="{high_y:.2f}" x2="{x:.2f}" y2="{low_y:.2f}" stroke="{color}" stroke-width="1.35" />')
        candle_shapes.append(
            f'<rect x="{x - body_width / 2:.2f}" y="{body_top:.2f}" width="{body_width:.2f}" height="{body_h:.2f}" '
            f'fill="{color}" stroke="{color}" rx="1" />'
        )

    overlay_shapes = []
    for level in payload.get("support_resistance", []):
        y = y_for_price(level["price"])
        color = escape(str(level.get("color") or "#38bdf8"))
        label = escape(str(level.get("label") or "S/R"))
        overlay_shapes.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + chart_w}" y2="{y:.2f}" stroke="{color}" stroke-width="1.25" stroke-dasharray="6 6" />')
        overlay_shapes.append(f'<text x="{left + 8}" y="{y - 8:.2f}" fill="{color}" font-size="12">{label}</text>')
    for zone in payload.get("fvg_zones", []):
        x1 = x_for_time(zone["start_time"])
        x2 = x_for_time(zone["end_time"])
        y1 = y_for_price(zone["high"])
        y2 = y_for_price(zone["low"])
        overlay_shapes.append(
            f'<rect x="{min(x1, x2):.2f}" y="{min(y1, y2):.2f}" width="{abs(x2 - x1):.2f}" height="{max(abs(y2 - y1), 4):.2f}" '
            'fill="rgba(250, 204, 21, 0.12)" stroke="rgba(250, 204, 21, 0.70)" stroke-width="1" />'
        )
    for line in payload.get("overlays", []):
        x1 = x_for_time(line["start_time"])
        x2 = x_for_time(line["end_time"])
        y1 = y_for_price(line["start_price"])
        y2 = y_for_price(line["end_price"])
        color = escape(str(line.get("color") or "#22d3ee"))
        label = escape(str(line.get("label") or line.get("kind") or "line"))
        overlay_shapes.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="2" />')
        overlay_shapes.append(f'<text x="{x2 + 6:.2f}" y="{y2 - 6:.2f}" fill="{color}" font-size="12">{label}</text>')
    for box in payload.get("risk_reward_boxes", []):
        x1 = x_for_time(box["start_time"])
        x2 = x_for_time(box["end_time"])
        entry_y = y_for_price(box["entry"])
        target_y = y_for_price(box["target"])
        stop_y = y_for_price(box["stop"])
        overlay_shapes.append(f'<rect x="{min(x1, x2):.2f}" y="{target_y:.2f}" width="{abs(x2 - x1):.2f}" height="{abs(entry_y - target_y):.2f}" fill="rgba(16,185,129,0.14)" stroke="rgba(16,185,129,0.75)" />')
        overlay_shapes.append(f'<rect x="{min(x1, x2):.2f}" y="{entry_y:.2f}" width="{abs(x2 - x1):.2f}" height="{abs(stop_y - entry_y):.2f}" fill="rgba(239,68,68,0.13)" stroke="rgba(239,68,68,0.75)" />')
        overlay_shapes.append(f'<line x1="{x1:.2f}" y1="{entry_y:.2f}" x2="{x2:.2f}" y2="{entry_y:.2f}" stroke="#e5e7eb" stroke-dasharray="4 4" />')

    symbol = escape(str(payload.get("symbol") or "TRAIDR"))
    interval = escape(str(payload.get("interval") or ""))
    mode = escape(str(payload.get("data_mode") or payload.get("metrics", {}).get("data_mode") or "preview"))
    last = float(candles[-1]["close"])
    return f"""
    <div class="traidr-static-chart">
      <div class="traidr-static-chart-header">
        <div><strong>{symbol}</strong> <span>{interval}</span> <span>{mode}</span></div>
        <div>Last {last:.4f} · can_execute_trades: false</div>
      </div>
      <svg class="traidr-candlestick-chart" viewBox="0 0 {width} {height}" role="img" aria-label="{symbol} candlestick chart">
        <rect x="0" y="0" width="{width}" height="{height}" rx="8" fill="#080b10" />
        <rect x="{left}" y="{top}" width="{chart_w}" height="{chart_h}" fill="#0a0f16" stroke="#263241" />
        {''.join(grid)}
        {''.join(labels)}
        {''.join(candle_shapes)}
        {''.join(overlay_shapes)}
      </svg>
    </div>
    """


def _render_cockpit(snapshot: BitunixCockpitSnapshot, *, data_mode: str, status_label: str) -> None:
    """Render the chart beside the intelligence stack."""

    _render_readouts(snapshot, label=status_label)
    chart_column, stack_column = st.columns([3.2, 1], gap="medium")
    with chart_column:
        render_chart(build_chart_payload(snapshot, data_mode=data_mode))
    with stack_column:
        _render_intelligence_stack(snapshot, data_mode=data_mode)


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


def _render_intelligence_stack(snapshot: BitunixCockpitSnapshot, *, data_mode: str) -> None:
    """Render product-facing market intelligence cards next to the chart."""

    depth_delta = float(snapshot.depth_delta.depth_delta_percent)
    funding = float(snapshot.funding_rate.funding_rate)
    opportunity = snapshot.opportunity_rating
    risk = snapshot.risk_rating
    market_state = _market_state(snapshot)
    next_action = _next_safe_action(snapshot, data_mode=data_mode)
    why_interesting = _why_interesting(snapshot)
    why_risky = _why_risky(snapshot, data_mode=data_mode)
    st.markdown(
        f"""
        <div class="traidr-panel">
          <h3>Intelligence Stack</h3>
          <p>Public market data only. can_execute_trades: false</p>
        </div>
        <div class="traidr-panel">
          <h3>Market State</h3>
          <p><strong>{market_state}</strong></p>
          <p>Mode: {data_mode}</p>
        </div>
        <div class="traidr-panel">
          <h3>Opportunity</h3>
          <p><strong>{opportunity}/100</strong></p>
          <p>{why_interesting}</p>
        </div>
        <div class="traidr-panel">
          <h3>Risk</h3>
          <p><strong>{risk}/100</strong></p>
          <p>{why_risky}</p>
        </div>
        <div class="traidr-panel">
          <h3>Liquidity / Depth</h3>
          <p><strong>{depth_delta:.2f}% bid share</strong></p>
          <p>{_depth_label(depth_delta)}</p>
        </div>
        <div class="traidr-panel">
          <h3>Funding State</h3>
          <p><strong>{funding:.5f}</strong></p>
          <p>{_funding_label(funding)}</p>
        </div>
        <div class="traidr-panel">
          <h3>Next Safe Action</h3>
          <p><strong>{next_action}</strong></p>
          <p>No order route exists in this cockpit.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_insufficient(reason_codes: list[str]) -> None:
    st.subheader("INSUFFICIENT_DATA")
    st.write("Reason codes:", ", ".join(reason_codes))
    st.write("can_execute_trades: false")


def _market_state(snapshot: BitunixCockpitSnapshot) -> str:
    start = float(snapshot.candles[0].close)
    end = float(snapshot.candles[-1].close)
    change = ((end - start) / start) * 100 if start else 0
    if change > 1.5 and snapshot.risk_rating < 55:
        return "SETUP IMPROVING"
    if change < -1.5 or snapshot.risk_rating >= 70:
        return "RISK RISING"
    return "NEUTRAL"


def _next_safe_action(snapshot: BitunixCockpitSnapshot, *, data_mode: str) -> str:
    if data_mode != "live_public_bitunix":
        return "Refresh public data"
    if snapshot.risk_rating >= 65:
        return "Review risk first"
    if snapshot.opportunity_rating >= 70:
        return "Monitor and confirm"
    return "Watch"


def _why_interesting(snapshot: BitunixCockpitSnapshot) -> str:
    reasons = []
    if snapshot.opportunity_rating >= 65:
        reasons.append("setup score is elevated")
    if float(snapshot.depth_delta.depth_delta_percent) > 55:
        reasons.append("bid-side depth is stronger")
    if float(snapshot.ticker.quote_volume) > 0:
        reasons.append("24h volume is available")
    return "; ".join(reasons) + "." if reasons else "No strong opportunity signal yet."


def _why_risky(snapshot: BitunixCockpitSnapshot, *, data_mode: str) -> str:
    reasons = []
    if data_mode != "live_public_bitunix":
        reasons.append("preview data is not actionable")
    if snapshot.risk_rating >= 50:
        reasons.append("risk score requires review")
    if abs(float(snapshot.funding_rate.funding_rate)) > 0.003:
        reasons.append("funding is elevated")
    if not reasons:
        reasons.append("research brackets are not trade instructions")
    return "; ".join(reasons) + "."


def _depth_label(depth_delta: float) -> str:
    if depth_delta >= 60:
        return "Bid dominant, but still research-only."
    if depth_delta <= 40:
        return "Ask pressure is elevated."
    return "Balanced book."


def _funding_label(funding: float) -> str:
    if abs(funding) < 0.001:
        return "Neutral funding."
    if funding > 0:
        return "Longs paying funding."
    return "Shorts paying funding."


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
