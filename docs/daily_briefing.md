# Daily Briefing

TRAIDR daily briefings summarize local DuckDB intelligence without adding any execution authority.

## Commands

```powershell
python -m cli.main briefing
python -m cli.main briefing --database storage/duckdb/traidr.duckdb
```

## Included Sections

- market scan summary
- top radar candidates
- highest-risk candidates
- new alerts
- recent paper simulation results
- current safety status
- missing data warnings
- suggested watchlist
- no execution actions

## Output States

- `RISK_ON`: local scan and radar data exist, a confident research candidate is present, and no high-risk override is detected.
- `NEUTRAL`: local data exists but does not justify risk-on or risk-off classification.
- `RISK_OFF`: high-risk radar candidates or critical alerts dominate.
- `INSUFFICIENT_DATA`: DuckDB is missing critical scan/radar evidence.

## Empty Database Behavior

If the database is missing or empty, the briefing prints helpful next commands such as:

```powershell
python -m cli.main scan --fixture --database storage/duckdb/traidr.duckdb
python -m cli.main scheduler-once --database storage/duckdb/traidr.duckdb
python scripts/run_simulation.py --database storage/duckdb/traidr.duckdb
```

## Safety

- Briefings are read-only.
- No trades, withdrawals, transfers, signing, custody, or private-key handling are introduced.
- The output always includes `can_execute_trades: False`.
- Suggested watchlists are research queues, not execution instructions.
