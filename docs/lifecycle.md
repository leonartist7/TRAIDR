# Candidate Lifecycle

Phase 37 tracks how TRAIDR radar candidates evolve over time.

## States

- `DISCOVERED`
- `WATCH`
- `ALERT`
- `BUY_CANDIDATE`
- `REVIEW`
- `AVOID`
- `STALE`
- `EXIT_RISK`

## Events

The lifecycle tracker detects:

- opportunity improving
- risk increasing
- liquidity improving
- liquidity draining
- stale data
- repeated candidate appearances
- candidate disappeared
- state changes

## Persistence

Lifecycle events are appended to DuckDB table `lifecycle_events` when a tracker is created with a DuckDB connection.

All lifecycle outputs include `can_execute_trades: false`. The tracker is research-only and cannot create orders, withdrawals, wallet operations, or live-trading actions.
