# Daily Run

Phase 39 adds one local command for TRAIDR's daily research workflow.

## Command

```bash
python -m cli.main daily-run --database storage/duckdb/traidr.duckdb
```

By default the command uses deterministic fixture scan data so it works offline:

```bash
python -m cli.main daily-run --database storage/duckdb/traidr.duckdb --fixture-scan
```

## Workflow

1. Status check.
2. Read-only fixture scan.
3. Watchlist update if local entries exist.
4. Radar update from scan candidates.
5. Local alert generation.
6. Daily briefing generation.
7. Summary printing.
8. Daily-run report persistence to DuckDB.

## Output

- what was scanned
- top opportunities
- top risks
- alerts generated
- missing data warnings
- next suggested commands
- `can_execute_trades: false`

## Safety Boundary

Daily run is local research only. It does not execute trades, create exchange orders, connect wallets, handle private keys, or require paid APIs.
