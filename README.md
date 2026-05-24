# TRAIDR

TRAIDR v3.1 is a local, simulation-first micro-cap crypto intelligence and paper-trading research engine. The MVP combines fixture-first observations, deterministic technical vectors, bounded mock agent research, DuckDB audit storage, and a deterministic risk gate before any paper action is recorded.

The current research layer also includes a personal market intelligence system: macro/news scoring, multi-agent CIO recommendations, ranked opportunity radar states, local alert history, and deterministic scheduler primitives. These outputs are recommendation-only and persisted locally in DuckDB.

## Safety Warning

This project is for simulation and research. It is not financial advice and must not be used as a live-trading or custody system.

Hard constraints:

- No live trades.
- No withdrawals.
- No private-key or seed phrase access.
- No secret exposure to LLM prompts or memory.
- No direct LLM order execution.
- Anti-rug hard fails override bullish signals.

## Simulation-Only Guarantee

The MVP defaults to simulation mode with `$50` of simulated capital. `HOLD` is the default decision. Missing, stale, malformed, contradictory, or uncertain required data must produce `INSUFFICIENT_DATA`.

Every future `BUY` or `SELL` intent must pass deterministic risk validation before it reaches a simulation broker. Optional GOAT SDK, DexScreener, or Hummingbot MCP work must preserve that boundary; Hummingbot use is limited to simulation or explicit testnet research.

## Setup

Use Python 3.11 for the target runtime.

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Run Simulation

Run one offline fixture simulation. It uses in-memory DuckDB by default and never calls a network API.

```bash
python scripts/run_simulation.py
```

To write the fixture paper records to the configured local DuckDB path and inspect them:

```bash
python scripts/run_simulation.py --database data/traidr.duckdb
python scripts/inspect_db.py
```

## CLI

Install the local command center:

```bash
python -m pip install -e .
```

Examples:

```bash
traidr status
traidr simulate
traidr inspect
traidr radar
traidr report --type daily
traidr alerts
traidr scan --fixture
traidr discover --fixture
traidr dashboard
traidr scheduler-once
```

`traidr dashboard` prints the Streamlit launch command instead of opening it automatically. See `docs/cli.md`.

CLI commands accept `--database` before or after the subcommand:

```bash
traidr inspect --database storage/duckdb/traidr_test.duckdb
```

## Dashboard

Run the read-only local dashboard after creating a local DuckDB file:

```bash
python scripts/run_simulation.py --database data/traidr.duckdb
python -m streamlit run dashboard/app.py
```

See `docs/dashboard.md` for details.

## Market Intelligence

TRAIDR can score local macro/news fixtures, combine structured non-executing agent analyses, rank watchlist opportunities, record local alert history, and run deterministic scheduler ticks from Python modules. The scheduler is intentionally a callable local research primitive, not a hidden daemon.

Key modules:

- `intelligence/` for macro regime, news scoring, and event calendar abstractions.
- `radar/` for watchlist ranking and opportunity states.
- `notifications/` for local alert history and optional injected ntfy, Telegram, or Discord transports.
- `scheduler/` for deterministic `1m`, `5m`, `15m`, `1h`, `4h`, and daily research task intervals.

See `docs/market_intelligence.md`, `docs/notifications.md`, and `docs/scheduler.md`.

## Market Scan

Run read-only fixture market scan and radar conversion:

```bash
python -m cli.main scan --fixture
python -m cli.main scan --fixture --database storage/duckdb/traidr_test.duckdb
python -m cli.main scan --source dexscreener --pair-ref solana/PAIR_ADDRESS
python -m cli.main radar --database storage/duckdb/traidr_test.duckdb
```

Real-source scan mode is optional and read-only. If data sources are unavailable or return no candidates, TRAIDR returns `INSUFFICIENT_DATA` or a clean no-candidates message rather than fabricating bullish data. See `docs/market_scan.md`.

## Token Discovery

Run offline discovery:

```bash
python -m cli.main discover --fixture
python -m cli.main discover --fixture --database storage/duckdb/traidr_discovery.duckdb
python -m cli.main discover --source dexscreener --limit 20
```

Discovery is research-only and cannot execute trades. See `docs/token_discovery.md`.

## Test

```bash
python -m pytest
```

## Optional Graphify Analysis

Graphify may be used as an optional dev-only repository analysis tool. It is not part of TRAIDR runtime dependencies and is scoped by `.graphifyignore` to avoid local environments, caches, storage artifacts, log output, DuckDB or Parquet files, and `.env` files.

See `docs/graphify.md` for the optional Codex and PowerShell workflow.

## Architecture Summary

TRAIDR uses explicit boundaries:

1. Free data adapters collect source observations.
2. The data pipeline validates freshness, shape, provenance, and confidence.
3. Technical and safety modules build deterministic vectors and anti-rug evidence.
4. Agents receive scrubbed TOON-compressed research payloads and return bounded intents.
5. The deterministic risk engine approves, rejects, or degrades decisions.
6. The simulation broker records paper-only portfolio changes in DuckDB.
7. Market intelligence modules persist recommendations, alerts, scheduler runs, and reports without execution authority.

See `SPEC.md`, `SAFETY_RULES.md`, and `IMPLEMENTATION_PLAN.md` before implementing runtime modules.

The MVP implementation is described further in `docs/architecture.md`, `docs/safety.md`, and `docs/decisions.md`.

## Not Implemented

- Live trading, exchange order routing, and live market loops.
- Withdrawals, transfers, bridging, custody, signing, or private-key handling.
- Real LLM provider calls.
- Paid APIs or key-required source adapters.
- Background autonomous notification daemons.
- Notification secrets or tokens stored by TRAIDR.

## Next Roadmap

The next safe increments are richer fixture and adapter coverage, config loading for local operator settings, portfolio snapshots, and deeper research reporting while preserving the deterministic risk and simulation boundaries.
