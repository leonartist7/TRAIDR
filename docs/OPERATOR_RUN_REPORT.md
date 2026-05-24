# Operator Run Report

Date: 2026-05-24

## Summary

Final operator verification passed after one CLI argument-order bug fix. TRAIDR remains local-first and simulation-only. No live trading, withdrawals, private-key handling, or AI direct execution behavior was added.

## Commands Run

| Command | Final Status | Result |
| --- | --- | --- |
| `python -m pytest` | PASS | `120 passed in 2.32s` |
| `python scripts/run_simulation.py` | PASS | In-memory simulation filled one paper BUY; orders=1, fills=1, audit_events=2 |
| `python scripts/run_simulation.py --database storage/duckdb/traidr_test.duckdb` | PASS | File-backed simulation filled one paper BUY; final script run showed orders=2, fills=2, audit_events=4 |
| `python scripts/inspect_db.py --database storage/duckdb/traidr_test.duckdb` | PASS | Listed 16 DuckDB tables and latest audit/order/fill records |
| `python -m cli.main status --database storage/duckdb/traidr_test.duckdb` | PASS | Reported simulation mode, local-only true, live trading false, withdrawals false, database exists true |
| `python -m cli.main simulate --database storage/duckdb/traidr_test.duckdb` | PASS | Paper simulation filled one BUY; final DB counts orders=3, fills=3, audit_events=6 |
| `python -m cli.main inspect --database storage/duckdb/traidr_test.duckdb` | PASS | Printed tables plus latest audit events, simulated orders, and simulated fills |
| `python -m cli.main radar --fixture --database storage/duckdb/traidr_test.duckdb` | PASS | Printed fixture radar `BUY_CANDIDATE` with `can_execute_trades: False` |
| `python -m cli.main report --database storage/duckdb/traidr_test.duckdb` | PASS | Printed daily fixture research summary because no stored report existed before scheduler run |
| `python -m cli.main alerts --database storage/duckdb/traidr_test.duckdb` | PASS | Printed `No local alert history found.` |
| `python -m cli.main scheduler-once --database storage/duckdb/traidr_test.duckdb` | PASS | Ran 6 due research tasks once and stored scheduler/report records |
| `python -m cli.main dashboard --database storage/duckdb/traidr_test.duckdb` | PASS | Printed manual Streamlit command without launching UI |

## Failure And Fix

Initial failure:

```text
usage: traidr [-h] [--database DATABASE]
              {status,simulate,inspect,radar,report,alerts,dashboard,scheduler-once} ...
traidr: error: unrecognized arguments: --database storage/duckdb/traidr_test.duckdb
```

Cause: `cli.main` accepted the global `--database` option only before the subcommand.

Fix applied: `cli.main` now normalizes `--database` when it appears after the subcommand, so both of these work:

```powershell
python -m cli.main --database storage/duckdb/traidr_test.duckdb status
python -m cli.main status --database storage/duckdb/traidr_test.duckdb
```

Test added: `tests/unit/test_cli_commands.py` now covers database override after the subcommand.

## Final Pytest Result

```text
120 passed in 2.32s
```

## Final Simulation Result

The deterministic simulation remained paper-only:

```text
Mode: simulation only
Pair: fixture-sol-usdc
Intent: BUY
Risk: APPROVED (RISK_APPROVED_SIMULATION_ONLY)
Execution: FILLED (SIMULATION_FILL_RECORDED)
```

The file-backed operator database accumulated repeated verification runs, ending with at least:

```text
orders=3
fills=3
audit_events=6
```

## Final CLI Results

- `status` confirms simulation mode, local-only behavior, no live trading, and no withdrawals.
- `simulate` routes through deterministic risk validation and records paper-only fills.
- `inspect` displays local DuckDB tables and latest paper records.
- `radar --fixture` displays research-only opportunity radar output with `can_execute_trades: False`.
- `report` safely falls back to a fixture daily report before stored reports exist.
- `alerts` handles empty local alert history gracefully.
- `scheduler-once` runs due local research tasks once and stores scheduler/report records.
- `dashboard` prints the Streamlit launch command and does not auto-launch.

## Remaining Limitations

- `storage/duckdb/traidr_test.duckdb` is generated local verification data and is ignored by git.
- Reports use fixture fallback until scheduler/report records are present in the selected DuckDB database.
- Alerts are empty until local alert records are created.
- Dashboard launch remains manual by design.
- Graphify CLI still works reliably through `python -m graphify`; `graphify.exe` may require adding the user Python Scripts directory to PATH.
