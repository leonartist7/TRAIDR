# Production Research Service

TRAIDR's production profile is an always-on, local research and paper-futures service. It reads public market data, writes one DuckDB database, computes explainable multi-horizon decisions, and exposes only three loopback controls: refresh, enable paper simulation, and disable paper simulation.

It has no exchange-order adapter, authenticated exchange endpoint, wallet integration, signing code, transfer path, or live-trading flag. `can_execute_trades` is always false.

## Supported Runtime

Use CPython 3.11. The doctor intentionally reports a failed release gate on any other Python version.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
python -m cli.main doctor --live
```

`doctor --live` makes a read-only public Bitunix connectivity check. It never asks for or reads credentials.

## Start on Windows

Open two PowerShell windows. From the repository root, activate the same virtual environment in both.

Window 1 — single-writer service:

```powershell
python -m cli.main service run --database data/traidr.duckdb
```

Window 2 — read-only dashboard:

```powershell
python -m streamlit run dashboard/app.py -- --database data/traidr.duckdb
```

Confirm service state from another terminal when needed:

```powershell
python -m cli.main service status --database data/traidr.duckdb
python -m cli.main paper positions --database data/traidr.duckdb
```

Stop the service with `Ctrl+C`. Shutdown is graceful: streams and local controls stop, pending writes finish, and a final heartbeat is recorded. TRAIDR does not silently install a Windows service, startup task, or background daemon.

## Safe Rollout

1. Keep auto paper simulation disabled and run collection-only shadow mode for at least 72 hours.
2. Inspect System Health for lag, gaps, reconnects, coverage, and degraded sources.
3. Use recommendations without paper positions until evidence and replay results are stable.
4. Enable local auto paper simulation explicitly from System Health only after the deterministic risk gates behave as expected.
5. Disable paper simulation immediately if accounting, feed quality, or model evidence is uncertain.

Enabling paper simulation cannot enable live trading. Each potential paper position must still pass the deterministic risk gate, freshness/depth/mark-index checks, portfolio limits, and simulator constraints.

## Data Modes

- `fixture`: offline contract and unit-test data; excluded from live views.
- `preview`: synthetic UI demonstration with a permanent watermark; never actionable.
- `live_public`: public network collection and validated production research.
- `replay`: deterministic historical reconstruction with no network access.

The live cockpit never substitutes preview candles after a provider failure. It displays `INSUFFICIENT_DATA` and the provider-specific reason codes.

## Durable State

The service owns all writes and batches state into `data/traidr.duckdb`. The dashboard opens read-only connections. Durable state includes instruments, candles, market events, data health, features, signals, risk assessments, outcomes, model/calibration metadata, paper orders/fills/positions/portfolios, controls, alerts, and heartbeats.

Every service restart restores the last paper portfolio and processed paper-signal keys. Repeated signals remain idempotent. Schema migrations are additive and idempotent.

Daily checkpointed backups are written to `data/backups` and retained for 14 days. Rotating structured service logs are written to `data/logs/traidr-service.jsonl`. Logs contain fixed event names and correlation IDs, not market payloads, credentials, environment dumps, or prompts.

## Research and Model Commands

```powershell
python -m cli.main replay --database data/traidr.duckdb
python -m cli.main backtest --database data/traidr.duckdb
```

Probabilities are hidden unless the applicable side/horizon bucket has at least 500 independent out-of-sample outcomes, expected calibration error is at most 5%, coverage is adequate, and no quality veto is active. Otherwise the dashboard shows `uncalibrated`, an opportunity score, coverage, and reason codes.

## Failure Runbook

- `DEGRADED` or `INSUFFICIENT_DATA`: do not infer a trade; inspect source/channel reason codes.
- Stale heartbeat: stop any abandoned process, run `doctor --live`, then restart the service.
- Stream gap: allow REST recovery; the gap must be backfilled or remain visibly recorded.
- DuckDB writer conflict: ensure only one `service run` process owns the database. Dashboard access must remain read-only.
- Python gate failure: create a Python 3.11 environment; do not publish a production release from another runtime.
- Calibration blocked: collect more independent outcomes; never promote or display a percentage manually.
- Paper drawdown halt: leave the halt in place, reconcile fills/funding/fees, and start a new reviewed simulation period rather than bypassing the limit.

No output is a profit guarantee or financial advice. The system is built to reduce false certainty, not to promise winning trades.
