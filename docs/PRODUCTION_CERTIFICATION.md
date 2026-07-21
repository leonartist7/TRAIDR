# TRAIDR Production Certification

Production certification is an evidence record, not a profitability claim. It covers public collection reliability,
data freshness, deterministic recovery, paper accounting, and auditability.

## Start and Observe

```powershell
.venv\Scripts\python.exe -m cli.main certify shadow --database data\traidr.duckdb
.venv\Scripts\python.exe -m cli.main service run --database data\traidr.duckdb
```

In another terminal:

```powershell
.venv\Scripts\python.exe -m cli.main certify status --database data\traidr.duckdb
.venv\Scripts\python.exe -m cli.main certify report --database data\traidr.duckdb
```

`certify shadow` is idempotent while a run is active. It records deterministic disconnect, malformed-frame,
duplicate, out-of-order, and rate-limit harness results. The service must still run for 72 continuous real hours;
the harness does not substitute for elapsed live observation.

## Pass Conditions

- No failed service heartbeat or uncaught service exit.
- Every injected public-stream fault recovers.
- At least 95% top-50 core coverage.
- Ticker p95 age below 15 seconds and one-minute candle age below 120 seconds.
- Gap states are always auditable as `DETECTED`, `BACKFILLING`, `RESOLVED`, or `UNRESOLVED`.
- No fixture, preview, expired-at-generation, or duplicate signal enters the live decision set.
- No paper order event occurs during collection-only shadow mode.
- Latest daily backup opens read-only with the complete expected schema.
- Two multi-day backtests produce the same SHA-256 replay hash.
- The DuckDB schema and idempotency constraints remain intact.

An incomplete report returns a non-zero command status by design. Do not tag or market the release as certified until
the report state is `PASSED`. Real-money execution remains forbidden regardless of certification state.
