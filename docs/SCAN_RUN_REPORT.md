# Scan Run Report

Date: 2026-05-24

## Summary

Phase 22 scan workflow verification passed. One gap was found and fixed: `radar` did not yet read scan-generated evidence from DuckDB, so it fell back to fixture radar output. The smallest safe fix now lets `radar` read latest `market_scan:*` evidence snapshots and display read-only scan-derived radar output.

No live trading, withdrawals, private-key handling, or execution from scan data was added.

## Commands Run

| Command | Status | Result |
| --- | --- | --- |
| `python -m pytest` | PASS | Initial result: `128 passed`; final result after fix: `129 passed` |
| `python -m cli.main scan --fixture` | PASS | Printed two fixture scan candidates and radar-from-scan rows, all with `can_execute_trades: False` |
| `python -m cli.main scan --fixture --database storage/duckdb/traidr_scan_test.duckdb` | PASS | Stored scan evidence in DuckDB and printed scan/radar output |
| `python -m cli.main inspect --database storage/duckdb/traidr_scan_test.duckdb` | PASS | Listed initialized tables; no execution/order/fill rows were present |
| `python -m cli.main radar --database storage/duckdb/traidr_scan_test.duckdb` | PASS | Displays `source: scan_evidence` with read-only non-executable radar rows |

## Failure And Fix

Observed behavior before the fix:

```text
python -m cli.main radar --database storage/duckdb/traidr_scan_test.duckdb
```

returned fixture radar output instead of reading scan-generated DuckDB evidence.

Fix applied:

- `cli.commands.radar()` now loads latest `market_scan:*` rows from `evidence_snapshots` when no persisted radar-state rows are present.
- The loaded scan evidence is converted through `scan_candidates_to_radar()`.
- Because stored scan evidence is sanitized and does not carry full normalized snapshots, radar remains conservative and outputs non-bullish `AVOID` rows with `can_execute_trades: False`.
- Added a unit test proving radar reads scan evidence from the database.

## Verification Note

During verification, one parallel run temporarily hit a DuckDB file lock:

```text
IO Error: Cannot open file "...traidr_scan_test.duckdb": The process cannot access the file because it is being used by another process.
```

The exact persisted scan command passed when rerun sequentially. TRAIDR CLI commands should be run one at a time against the same local DuckDB file.

## Final Pytest Result

```text
129 passed
```

## Remaining Limitations

- Real-source scan mode remains optional and read-only.
- Without configured/injected real data sources, real-source scan returns `INSUFFICIENT_DATA`.
- Scan evidence loaded from DuckDB is intentionally conservative because stored evidence is sanitized; it does not create executable or bullish trade actions.
- No scan output can execute trades.
