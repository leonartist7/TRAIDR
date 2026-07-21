# TRAIDR Operator Guide

Date: 2026-07-21

## First Run Setup

Use Python 3.11 as the target runtime, then install dependencies locally:

```bash
uv venv .venv --python 3.11
.venv\Scripts\activate
python -m pip install -r requirements.lock
```

Verify the environment:

```bash
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy intelligence data_pipeline execution risk scoring storage config
python -m cli.main doctor --live
python -m cli.main status
```

For the always-on public research service, use the two-terminal Windows procedure in `docs/PRODUCTION_RESEARCH_SERVICE.md`.

## Daily Workflow

A safe daily local workflow is:

```bash
python -m cli.main status
python -m cli.main daily-run --database storage/duckdb/traidr.duckdb
python -m cli.main briefing --database storage/duckdb/traidr.duckdb
python -m cli.main radar --database storage/duckdb/traidr.duckdb
python -m cli.main alerts --database storage/duckdb/traidr.duckdb
```

Legacy write commands should still run one at a time. In production mode, `service run` is the only writer and the dashboard remains read-only.

## Fixture Scan

Fixture mode works offline and is the safest smoke test:

```bash
python -m cli.main scan --fixture
python -m cli.main scan --fixture --database storage/duckdb/traidr_scan.duckdb
python -m cli.main radar --database storage/duckdb/traidr_scan.duckdb
```

Scan and radar outputs are research-only and include `can_execute_trades: false` where relevant.

## Real Read-Only Sources

Real-source modes are optional, read-only, and fail closed:

```bash
python -m cli.main scan --source dexscreener --pair-ref solana/PAIR_ADDRESS
python -m cli.main discover --source dexscreener --limit 20
python -m cli.main token --pair-ref solana/PAIR_ADDRESS --source dexscreener
python -m cli.main news --source rss
python -m cli.main macro
```

If a source is missing, stale, malformed, unavailable, or incomplete, TRAIDR returns `INSUFFICIENT_DATA` rather than inventing bullish evidence.

## Inspect DuckDB

Use inspect to confirm what TRAIDR stored locally:

```bash
python -m cli.main inspect --database storage/duckdb/traidr.duckdb
```

The inspect command lists tables and recent audit/order/fill records. It does not execute actions.

## Dashboard

The dashboard is the easiest way to use TRAIDR without typing the underlying workflow commands:

```bash
python -m cli.main dashboard
python -m streamlit run dashboard/app.py -- --database storage/duckdb/traidr.duckdb
```

The production dashboard is read-only. Its only state-changing controls call the loopback research service for
refresh, paper enable, or paper disable. No exchange, wallet, credential, transfer, or arbitrary command endpoint exists.

## Production Certification

Run collection-only shadow mode with paper simulation disabled:

```bash
python -m cli.main certify shadow --database data/traidr.duckdb
python -m cli.main service run --database data/traidr.duckdb
python -m cli.main certify status --database data/traidr.duckdb
python -m cli.main certify report --database data/traidr.duckdb
```

Certification cannot pass before 72 real hours, fresh top-50 coverage, recoverable backups, and repeatable
multi-day replay hashes are present. Probability remains `uncalibrated` until a side/horizon bucket has at least
500 independent out-of-sample outcomes and calibration error at or below 5%.

## Alerts

Alerts are local-first:

```bash
python -m cli.main alerts
python -m cli.main alerts rules
python -m cli.main alerts test
```

Optional external notification senders use injected transports. Missing tokens or webhooks do not enable execution.

## Portfolio And Watchlist

Manual portfolio and watchlist commands are local research tools:

```bash
python -m cli.main watch list
python -m cli.main watch add solana/PAIR_ADDRESS --note "watch liquidity"
python -m cli.main portfolio list
python -m cli.main portfolio report
python -m cli.main portfolio monitor
python -m cli.main portfolio sell-risk
```

They do not connect to wallets or exchanges.

## Ask TRAIDR

Ask TRAIDR answers local DuckDB summary questions without an external LLM:

```bash
python -m cli.main ask "show best radar candidates"
python -m cli.main ask "what are my top risks?"
python -m cli.main ask "show recent alerts"
python -m cli.main ask "what should I watch today?"
```

Unknown questions return suggestions instead of taking actions.

## Troubleshooting

- DuckDB file lock: confirm only one research service owns the database; the production dashboard uses read-only connections.
- Empty radar: run `scan --fixture --database <path>` or `daily-run --database <path>` first.
- Empty briefing: run `daily-run --database <path>` or collect scan/radar/alert evidence first.
- Real-source failure: treat `INSUFFICIENT_DATA` as expected fail-closed behavior and retry later.
- Import or dependency errors: reactivate the virtual environment and rerun `python -m pip install -r requirements.txt`.

## What TRAIDR Cannot Do

- It cannot place live trades.
- It cannot withdraw, transfer, bridge, or custody assets.
- It cannot sign transactions or access private keys, seed phrases, or exchange secrets.
- It cannot execute from AI, LLM, alert, scan, radar, dashboard, daily-run, watchlist, or portfolio output.
- It is not financial advice.

## Safety Model

TRAIDR is simulation-first, local-first, DuckDB-backed, and fail-closed. Real-world data adapters are read-only. Simulation orders require deterministic risk approval before the paper broker records anything. `HOLD` and `INSUFFICIENT_DATA` never execute. Anti-rug hard failures override bullish signals.
