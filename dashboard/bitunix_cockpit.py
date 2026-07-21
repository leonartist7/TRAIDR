"""Bitunix read-only futures cockpit for the Streamlit dashboard."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Any

import duckdb
import streamlit as st
import streamlit.components.v1 as components

from data_pipeline.bitunix_futures_adapter import BitunixFuturesAdapter
from data_pipeline.bitunix_models import (
    BITUNIX_ALLOWED_DEPTH_LIMITS,
    BITUNIX_ALLOWED_INTERVALS,
    BITUNIX_INTERVAL_SECONDS,
    BitunixAdapterResult,
    BitunixCandle,
    BitunixCockpitSnapshot,
    BitunixDepthSnapshot,
    BitunixFundingRate,
    BitunixOrderBookLevel,
    BitunixTicker,
)
from intelligence.production_models import SignalDecision, SignalDirection
from scoring.signal_engine import score_directional_setup
from technicals.multi_horizon import build_multi_horizon_features

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

    symbols = _available_symbols(database_path)
    control_columns = st.columns([1, 1, 1, 1, 1])
    symbol = control_columns[0].selectbox("Pair", symbols, index=0)
    interval = control_columns[1].selectbox("Interval", BITUNIX_ALLOWED_INTERVALS, index=3)
    depth_limit = control_columns[2].selectbox("Depth", BITUNIX_ALLOWED_DEPTH_LIMITS, index=2)
    data_mode = control_columns[3].selectbox("Data mode", ("live_public", "preview"), index=0)
    auto_refresh = control_columns[4].toggle(
        "Live refresh",
        value=False,
        help="Refresh validated public data every 10 seconds while this page is open.",
    )

    if data_mode == "preview":
        st.warning("PREVIEW MODE — synthetic demonstration data; never actionable.")
        _render_cockpit(
            build_preview_snapshot(symbol, interval),
            data_mode="preview",
            status_label="PREVIEW — SYNTHETIC",
        )
        return

    session_key = f"bitunix:{symbol}:{interval}:{depth_limit}"
    if auto_refresh:
        _render_auto_refresh(database_path, symbol, interval, depth_limit)
        return

    if st.button("Refresh Real Bitunix Data", type="primary", use_container_width=True):
        with st.spinner("Fetching public Bitunix futures data..."):
            result = _run_async(BitunixFuturesAdapter().fetch_cockpit_snapshot(symbol, interval, depth_limit))
        st.session_state[session_key] = result
        if result.ok:
            st.success("Read-only Bitunix data loaded.")
        else:
            st.error("Bitunix data is insufficient. No bullish data was fabricated.")

    result = st.session_state.get(session_key)
    if result is None:
        st.info("Press Refresh Real Bitunix Data to load validated public market evidence.")
        render_chart(insufficient_chart_payload(("LIVE_REFRESH_REQUIRED",)))
        return
    if not isinstance(result, BitunixAdapterResult) or not result.ok or not isinstance(result.value, BitunixCockpitSnapshot):
        reason_codes = list(getattr(result, "reason_codes", ("BITUNIX_INSUFFICIENT_DATA",)))
        _render_insufficient(reason_codes)
        render_chart(insufficient_chart_payload(reason_codes))
        return

    snapshot = result.value
    _render_cockpit(
        snapshot,
        data_mode="live_public_bitunix",
        status_label="Live public Bitunix data",
        paper_positions=_paper_positions(database_path, symbol),
        paper_fills=_paper_fills(database_path, symbol),
    )


def _available_symbols(database_path: str | Path) -> tuple[str, ...]:
    """Return the locally discovered perpetual universe without opening a writer."""

    path = Path(database_path)
    defaults = ("BTCUSDT", "HYPEUSDT")
    if not path.exists():
        return defaults
    try:
        with duckdb.connect(str(path), read_only=True) as connection:
            rows = connection.execute(
                """
                SELECT symbol
                FROM market_instruments
                WHERE status = 'OPEN' AND quote_asset = 'USDT'
                ORDER BY symbol
                """
            ).fetchall()
    except (duckdb.Error, OSError):
        return defaults
    discovered = tuple(str(row[0]) for row in rows if row and row[0])
    ordered = tuple(symbol for symbol in defaults if symbol in discovered)
    remainder = tuple(symbol for symbol in discovered if symbol not in ordered)
    return ordered + remainder if discovered else defaults


def _paper_positions(database_path: str | Path, symbol: str) -> tuple[dict[str, Any], ...]:
    path = Path(database_path)
    if not path.exists():
        return ()
    try:
        with duckdb.connect(str(path), read_only=True) as connection:
            rows = connection.execute(
                """
                SELECT position_json
                FROM paper_futures_positions
                WHERE instrument_id = ? AND status = 'OPEN'
                ORDER BY updated_at DESC
                """,
                [f"bitunix:{symbol}"],
            ).fetchall()
    except (duckdb.Error, OSError):
        return ()
    overlays: list[dict[str, Any]] = []
    for row in rows:
        try:
            item = json.loads(str(row[0]))
            overlays.append(
                {
                    "position_id": str(item["position_id"]),
                    "direction": str(item["direction"]),
                    "entry": float(item["entry_price"]),
                    "mark": float(item["mark_price"]),
                    "stop": float(item["stop_price"]),
                    "liquidation": float(item["liquidation_price"]),
                }
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return tuple(overlays)


def _paper_fills(database_path: str | Path, symbol: str) -> tuple[dict[str, Any], ...]:
    path = Path(database_path)
    if not path.exists():
        return ()
    try:
        with duckdb.connect(str(path), read_only=True) as connection:
            rows = connection.execute(
                """
                SELECT f.filled_at, f.fill_price, o.direction
                FROM paper_futures_fills f
                JOIN paper_futures_orders o ON o.order_id = f.order_id
                WHERE o.instrument_id = ?
                ORDER BY f.filled_at DESC
                LIMIT 100
                """,
                [f"bitunix:{symbol}"],
            ).fetchall()
    except (duckdb.Error, OSError):
        return ()
    return tuple(
        {
            "time": int(_as_utc(row[0]).timestamp()),
            "price": float(row[1]),
            "direction": str(row[2]),
        }
        for row in rows
    )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _render_auto_refresh(
    database_path: str | Path,
    symbol: str,
    interval: str,
    depth_limit: int,
) -> None:
    """Render a ten-second live fragment using public endpoints only."""

    @st.fragment(run_every="10s")
    def live_fragment() -> None:
        result = _run_async(BitunixFuturesAdapter().fetch_cockpit_snapshot(symbol, interval, depth_limit))
        if not result.ok or not isinstance(result.value, BitunixCockpitSnapshot):
            reason_codes = list(result.reason_codes or ("BITUNIX_INSUFFICIENT_DATA",))
            _render_insufficient(reason_codes)
            render_chart(insufficient_chart_payload(reason_codes))
            return
        st.caption(f"Auto-refreshed at {datetime.now(tz=UTC).isoformat(timespec='seconds')}")
        _render_cockpit(
            result.value,
            data_mode="live_public_bitunix",
            status_label="Live public Bitunix data",
            paper_positions=_paper_positions(database_path, symbol),
            paper_fills=_paper_fills(database_path, symbol),
        )

    live_fragment()


def build_chart_payload(
    snapshot: BitunixCockpitSnapshot,
    *,
    data_mode: str = "live_public_bitunix",
    paper_positions: tuple[dict[str, Any], ...] = (),
    paper_fills: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """Build the chart payload consumed by chart_engine.js."""

    candles = snapshot.chart_candles()
    support_resistance = _support_resistance(snapshot.candles)
    overlays = _trend_overlays(snapshot.candles)
    fvg_zones = _fair_value_gaps(snapshot.candles)
    signal = _cockpit_signal(snapshot, data_mode=data_mode)
    risk_reward_boxes = _signal_risk_reward_boxes(signal, snapshot.candles)
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
            "opportunity_rating": signal.opportunity_score if signal else snapshot.opportunity_rating,
            "risk_rating": signal.risk_score if signal else snapshot.risk_rating,
            "direction": signal.direction.value if signal else "NO_TRADE",
            "probability_state": signal.probability_state.value if signal else "UNCALIBRATED",
            "success_probability": signal.success_probability if signal else None,
        },
        "signal": signal.model_dump(mode="json") if signal else None,
        "paper_positions": list(paper_positions),
        "paper_fills": list(paper_fills),
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
    interval_seconds = BITUNIX_INTERVAL_SECONDS.get(interval, 3600)
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
            indexPrice=str(last),
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


def render_chart(payload: dict[str, Any]) -> None:
    """Render the locally bundled interactive chart without a network dependency."""

    engine = CHART_ENGINE_PATH.read_text(encoding="utf-8")
    safe_payload = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    components.html(
        f"""
        <div id="traidr-bitunix-chart"></div>
        <script>{engine}</script>
        <script>
          window.renderTRAIDRBitunixChart("traidr-bitunix-chart", {safe_payload});
        </script>
        """,
        height=700,
        scrolling=False,
    )


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


def _render_cockpit(
    snapshot: BitunixCockpitSnapshot,
    *,
    data_mode: str,
    status_label: str,
    paper_positions: tuple[dict[str, Any], ...] = (),
    paper_fills: tuple[dict[str, Any], ...] = (),
) -> None:
    """Render the chart beside the intelligence stack."""

    payload = build_chart_payload(
        snapshot,
        data_mode=data_mode,
        paper_positions=paper_positions,
        paper_fills=paper_fills,
    )
    _render_readouts(snapshot, label=status_label, payload=payload)
    chart_column, stack_column = st.columns([3.2, 1], gap="medium")
    with chart_column:
        render_chart(payload)
    with stack_column:
        _render_intelligence_stack(snapshot, data_mode=data_mode, payload=payload)


def _render_readouts(snapshot: BitunixCockpitSnapshot, *, label: str, payload: dict[str, Any]) -> None:
    st.subheader(f"{snapshot.symbol} · {snapshot.interval} · {label}")
    metrics = st.columns(5)
    metrics[0].metric("Last", f"{float(snapshot.ticker.last_price):,.4f}")
    metrics[1].metric("24h High", f"{float(snapshot.ticker.high):,.4f}")
    metrics[2].metric("24h Low", f"{float(snapshot.ticker.low):,.4f}")
    metrics[3].metric("Depth Delta", f"{float(snapshot.depth_delta.depth_delta_percent):.2f}%")
    metrics[4].metric("Funding", f"{float(snapshot.funding_rate.funding_rate):.5f}")

    score_columns = st.columns(4)
    metrics_payload = payload.get("metrics", {})
    score_columns[0].metric("Direction", metrics_payload.get("direction", "NO_TRADE"))
    score_columns[1].metric("Opportunity Rating", metrics_payload.get("opportunity_rating", snapshot.opportunity_rating))
    score_columns[2].metric("Safety Risk", metrics_payload.get("risk_rating", snapshot.risk_rating))
    score_columns[3].metric("Probability", _probability_label(metrics_payload))
    st.write("Reason codes:", ", ".join(snapshot.reason_codes))


def _render_intelligence_stack(
    snapshot: BitunixCockpitSnapshot,
    *,
    data_mode: str,
    payload: dict[str, Any],
) -> None:
    """Render product-facing market intelligence cards next to the chart."""

    depth_delta = float(snapshot.depth_delta.depth_delta_percent)
    funding = float(snapshot.funding_rate.funding_rate)
    metrics_payload = payload.get("metrics", {})
    opportunity = metrics_payload.get("opportunity_rating", snapshot.opportunity_rating)
    risk = metrics_payload.get("risk_rating", snapshot.risk_rating)
    direction = metrics_payload.get("direction", "NO_TRADE")
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
          <p><strong>{market_state} · {direction}</strong></p>
          <p>Mode: {data_mode}</p>
        </div>
        <div class="traidr-panel">
          <h3>Opportunity</h3>
          <p><strong>{opportunity}/100</strong></p>
          <p>{why_interesting}</p>
          <p>Probability: {_probability_label(metrics_payload)}</p>
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


def _cockpit_signal(snapshot: BitunixCockpitSnapshot, *, data_mode: str) -> SignalDecision | None:
    if data_mode != "live_public_bitunix" or snapshot.interval == "1m":
        return None
    bid = snapshot.depth.bids[0].price
    ask = snapshot.depth.asks[0].price
    midpoint = (bid + ask) / Decimal("2")
    spread_bps = float((ask - bid) / midpoint * Decimal("10000")) if midpoint > 0 else None
    depth_imbalance = float(snapshot.depth_delta.depth_delta_percent / Decimal("50") - Decimal("1"))
    funding = snapshot.funding_rate
    basis_bps = float(
        (funding.mark_price - funding.index_price) / funding.index_price * Decimal("10000")
    )
    feature_result = build_multi_horizon_features(
        instrument_id=f"bitunix:{snapshot.symbol}",
        horizon=snapshot.interval,
        candles=snapshot.candles,
        evidence_ids=(f"cockpit:{snapshot.symbol}:{snapshot.interval}:{snapshot.candles[-1].time_ms}",),
        depth_imbalance=depth_imbalance,
        spread_bps=spread_bps,
        funding_rate=float(funding.funding_rate),
        basis_bps=basis_bps,
        now=snapshot.observed_at,
    )
    if not feature_result.ok or feature_result.value is None:
        return None
    feature = feature_result.value.model_copy(
        update={
            "data_coverage": min(feature_result.value.data_coverage, 0.70),
            "missing_features": (
                *feature_result.value.missing_features,
                "cross_market_evidence",
                "news_context",
                "onchain_safety",
            ),
            "quality_warnings": (
                *feature_result.value.quality_warnings,
                "COCKPIT_DIRECT_REFRESH_PARTIAL_COVERAGE",
            ),
        }
    )
    return score_directional_setup(feature, token_safety_required=False)


def _signal_risk_reward_boxes(
    signal: SignalDecision | None,
    candles: tuple[BitunixCandle, ...],
) -> list[dict[str, Any]]:
    if (
        signal is None
        or signal.direction is SignalDirection.NO_TRADE
        or signal.stop is None
        or not signal.targets
        or signal.entry_low is None
        or signal.entry_high is None
        or len(candles) < 2
    ):
        return []
    entry = float((signal.entry_low + signal.entry_high) / Decimal("2"))
    end_time = int(candles[-1].time_ms / 1000)
    start_time = int(candles[max(0, len(candles) - 12)].time_ms / 1000)
    return [
        {
            "label": f"{signal.direction.value} research bracket",
            "start_time": start_time,
            "end_time": end_time,
            "entry": entry,
            "target": float(signal.targets[0]),
            "stop": float(signal.stop),
        }
    ]


def _probability_label(metrics: dict[str, Any]) -> str:
    probability = metrics.get("success_probability")
    if probability is None or metrics.get("probability_state") != "CALIBRATED":
        return "uncalibrated"
    return f"{float(probability):.1%}"


def _run_async(awaitable: Any) -> Any:
    return asyncio.run(awaitable)
