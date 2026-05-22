# MVP Cutline

## Day-1 MVP Required

Day-1 MVP means a local simulation path that is safe before it is clever.

- Python 3.11 project bootstrap.
- Validated settings with simulation as the only permitted MVP mode.
- `$50` simulated starting capital.
- DuckDB local persistence for core audit records.
- Deterministic intent, risk decision, and simulated broker contracts.
- Deterministic anti-rug hard-fail checks.
- `HOLD` fallback and `INSUFFICIENT_DATA` failure behavior.
- A minimal technical vector path from validated snapshots.
- A local paper-trade scenario driven by fixtures or free-source-safe snapshots.
- Safety and integration tests run with `pytest`.

## Safe to Stub

Stubs must fail closed and advertise their limits.

- Optional DexScreener adapter until adapter contracts and fixtures are stable.
- Optional GOAT SDK data adapter.
- Optional sentiment features.
- Research-agent prompt tuning.
- Scrubbed research memory.
- Database inspection helper script.
- Hummingbot MCP integration, provided no runtime path pretends it is available.
- Testnet boundary, provided it cannot be selected by MVP defaults.

## Must Never Be Stubbed

The following cannot be replaced by optimistic placeholders:

- Live-trading prohibition.
- Withdrawal prohibition.
- Secret isolation from LLM and storage payloads.
- Deterministic risk validation before any simulated action.
- Anti-rug veto priority.
- Data freshness and malformed-data handling.
- `HOLD` default behavior.
- `INSUFFICIENT_DATA` for missing, stale, malformed, contradictory, or uncertain required data.
- Broker rejection of unapproved instructions.

## Deferred to Phase 2

Here `Phase 2` means the post-MVP product increment, not `BUILD_PHASES.md` Phase 2 core utilities.

- Broader free-source coverage and adapter hardening.
- Testnet-only experiments under the same deterministic safety gate.
- Optional Hummingbot MCP simulation/testnet workflows.
- GOAT SDK and DexScreener enhancements after contracts are stable.
- Expanded sentiment, memory, scheduling, analytics, and diagnostics.
- More chains, pairs, anti-rug evidence types, and portfolio scenario research.
- Deployment, production operations, paid feeds, and multi-user features.

## Permanently Out

- Live trades.
- Withdrawals.
- Private-key handling.
- LLM direct order execution.

