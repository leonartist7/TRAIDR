# TRAIDR

TRAIDR v3.1 is a local, simulation-first micro-cap crypto intelligence and paper-trading research engine. It is planned to combine free-source observations, deterministic feature vectors, bounded agent research, DuckDB audit storage, and a deterministic risk gate before any paper action is recorded.

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

Setup commands will be added during the bootstrap phase.

```bash
# placeholder: create a Python 3.11 environment and install local dependencies
```

## Run

The local simulation command will be added after the simulation broker exists.

```bash
# placeholder: run the local simulation research loop
```

## Test

```bash
pytest
```

## Architecture Summary

TRAIDR is planned around explicit boundaries:

1. Free data adapters collect source observations.
2. The data pipeline validates freshness, shape, provenance, and confidence.
3. Technical and safety modules build deterministic vectors and anti-rug evidence.
4. Agents receive scrubbed TOON-compressed research payloads and return bounded intents.
5. The deterministic risk engine approves, rejects, or degrades decisions.
6. The simulation broker records paper-only portfolio changes in DuckDB.

See `SPEC.md`, `SAFETY_RULES.md`, and `IMPLEMENTATION_PLAN.md` before implementing runtime modules.
