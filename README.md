# TRAIDR

TRAIDR v3.1 is a local, simulation-first micro-cap crypto intelligence and paper-trading research engine. The MVP combines fixture-first observations, deterministic technical vectors, bounded mock agent research, DuckDB audit storage, and a deterministic risk gate before any paper action is recorded.

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

See `SPEC.md`, `SAFETY_RULES.md`, and `IMPLEMENTATION_PLAN.md` before implementing runtime modules.

The MVP implementation is described further in `docs/architecture.md`, `docs/safety.md`, and `docs/decisions.md`.

## Not Implemented

- Live trading, exchange order routing, and live market loops.
- Withdrawals, transfers, bridging, custody, signing, or private-key handling.
- Real LLM provider calls.
- Paid APIs or key-required source adapters.

## Next Roadmap

The next safe increments are richer fixture and adapter coverage, config loading for local operator settings, portfolio snapshots, and deeper research reporting while preserving the deterministic risk and simulation boundaries.
