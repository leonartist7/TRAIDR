# Bitunix Futures Cockpit

Phase 42 adds a native TRAIDR futures research cockpit for Bitunix public futures data.

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

Open the `Bitunix Futures` tab, choose a pair and interval, then press `Refresh Bitunix Public Data`.

The first version supports:

- `HYPEUSDT`
- `BTCUSDT`
- `1m`, `5m`, `15m`, `1h`
- public tickers
- public klines
- public funding rate
- public order book depth

## Chart Engine

The cockpit renders a native Lightweight Charts canvas loaded from CDN. It does not use screenshots and does not embed the Bitunix trading UI.

The overlay layer draws:

- trend / break-of-structure vector
- fair value gap zones
- support and resistance levels
- research-only risk/reward brackets

## Failure Behavior

If Bitunix is unavailable, returns malformed data, omits required fields, returns stale candles, or has empty depth, TRAIDR shows `INSUFFICIENT_DATA` and does not fabricate bullish signals.
