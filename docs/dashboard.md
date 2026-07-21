# Dashboard

TRAIDR includes a local, read-only Streamlit cockpit for live public research, evidence inspection, paper-futures state, and system health.

## Run

Start the single-writer service and dashboard in separate terminals:

```bash
python -m cli.main service run --database data/traidr.duckdb
python -m streamlit run dashboard/app.py -- --database data/traidr.duckdb
```

The CLI dashboard command prints the launch command instead of opening a UI automatically:

```bash
python -m cli.main dashboard
```

## Layout

- `Cockpit`: locally bundled interactive chart, live public refresh, signal evidence, plan levels, gaps, and paper overlays.
- `Operations`: read-only database, safety, and service-start guidance.
- `Radar`: current deduplicated signal decisions ranked by expected value, coverage, freshness, and risk.
- `Token Detail`: local token evidence, technical vectors, and anti-rug state.
- `Watchlist`: locally watched identities.
- `Portfolio`: perpetual-futures paper positions, fills, margin, costs, P&L, and drawdown.
- `Alerts`: deduplicated local alert history.
- `Reports`: local research and calibration reports.
- `Safety Status`: explicit forbidden-capability posture.
- `System Health`: heartbeats, source/channel freshness, reconnects, gaps, calibration state, and loopback controls.

Risk and data-quality evidence is shown before opportunity evidence where both exist.

## Controls

Production database writes do not run inside Streamlit. The System Health buttons call the allowlisted local service API at `127.0.0.1:8765` for only:

- refresh research data;
- enable deterministic local paper simulation;
- disable deterministic local paper simulation.

The control API has no signal, order, leverage, credential, wallet, transfer, or withdrawal endpoint. Enabling paper mode still requires the final deterministic risk gate for every simulated position.

## Cockpit

The cockpit supports manual refresh or a ten-second public-data refresh loop. Its canvas engine is bundled in the repository and has no CDN dependency. It renders candles, volume, crosshair, pan/zoom, support/resistance, fair-value gaps, signal brackets, visible data gaps, paper fills, and paper position/stop/liquidation levels.

Preview data appears only when `preview` is selected and is permanently watermarked. Provider failure, stale evidence, or malformed data displays `INSUFFICIENT_DATA`; preview candles are never substituted into live mode.

## Missing Database

If the configured database is missing, start `python -m cli.main service run`. The service performs additive schema initialization and becomes the database's sole writer.

## Safety Boundary

The dashboard has no exchange-order, withdrawal, signing, key, authenticated-exchange, or live-execution capability. Research and paper records carry `can_execute_trades: false` where applicable. See `docs/PRODUCTION_RESEARCH_SERVICE.md` for the operator runbook.
