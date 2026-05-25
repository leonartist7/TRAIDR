# Watchlist

TRAIDR watchlists are local, user-managed research queues stored in DuckDB. They do not create execution actions.

## Commands

```powershell
python -m cli.main watch add solana/PAIR_ADDRESS --note "watch liquidity"
python -m cli.main watch add solana/PAIR_ADDRESS --note "new pair" --tag solana --tag meme
python -m cli.main watch list
python -m cli.main watch remove solana/PAIR_ADDRESS
python -m cli.main watch scan
```

All commands also accept `--database` before or after the command:

```powershell
python -m cli.main watch add solana/PAIR_ADDRESS --note "watch" --database storage/duckdb/traidr.duckdb
python -m cli.main watch scan --database storage/duckdb/traidr.duckdb
```

## Stored Fields

Each active entry stores:

- `pair_ref`
- `note`
- `tags`
- `created_at`
- `active`
- `can_execute_trades: False`

Watch scans append local scan records with radar state, opportunity score, risk score, reason codes, and `can_execute_trades: False`.

## Alert Behavior

`watch scan` runs the active entries through read-only market scan and radar scoring. If the latest score changes materially from the prior watch scan, TRAIDR writes a local alert:

- `WATCH_RISK_WORSENED` when risk rises.
- `WATCH_OPPORTUNITY_IMPROVED` when opportunity improves.

Alerts are local DuckDB records only. They are not execution instructions.

## Safety

- No live trading.
- No withdrawals, transfers, custody, signing, or private-key handling.
- Watchlist scan uses read-only data boundaries.
- No watchlist command can execute trades.
