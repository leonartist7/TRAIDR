# Bitunix Futures Cockpit

The native TRAIDR futures research cockpit displays validated Bitunix public futures data and locally computed evidence.

## Safety Boundary

- Public Bitunix futures market data only.
- No Bitunix private endpoints.
- No API keys, API secrets, signatures, account reads, positions, leverage, margin changes, orders, close-position calls, transfers, or withdrawals.
- No iframe embedding of Bitunix.
- All cockpit payloads include `can_execute_trades: false`.

## Dashboard Use

Start the dashboard:

```bash
python -m streamlit run dashboard/app.py
```

Open the `Bitunix Futures` tab, choose a discovered pair and interval, then press `Refresh Real Bitunix Data`. Enable `Live refresh` for a validated ten-second refresh loop.

The cockpit supports:

- the service-discovered open USDT perpetual universe, with BTC and HYPE defaults before discovery
- `1m`, `5m`, `15m`, `1h`, `4h`, and `1d`
- public tickers
- public klines
- public funding rate
- public order book depth

## Chart Engine

The cockpit renders a locally bundled, pinned canvas engine. It makes no CDN request, uses no screenshots, and does not embed the Bitunix trading UI.

The overlay layer draws:

- trend / break-of-structure vector
- fair value gap zones
- support and resistance levels
- research-only risk/reward brackets
- crosshair, zoom, pan, volume, visible gaps, signal expiry, and paper-position overlays

Preview data is available only through the explicit `preview` data mode and is permanently watermarked. It is never substituted for failed live data.

## Failure Behavior

If Bitunix is unavailable, returns malformed data, omits required fields, returns stale candles, or has empty depth, TRAIDR shows `INSUFFICIENT_DATA` and does not fabricate bullish signals.
