# Alert Rules

TRAIDR alert rules turn local research changes into local notification history. They do not execute trades.

## Commands

```powershell
python -m cli.main alerts
python -m cli.main alerts test
python -m cli.main alerts rules
```

`alerts` shows local alert history from DuckDB. `alerts rules` lists configured research triggers. `alerts test` runs deterministic fixture changes through the rule engine and records local-only alert history.

## Triggers

- opportunity score increased meaningfully
- risk score increased meaningfully
- liquidity dropped
- liquidity increased
- token moved `WATCH` to `ALERT`
- token moved `ALERT` to `BUY_CANDIDATE`
- token moved from any non-`AVOID` state to `AVOID`
- scan data became stale
- safety data is incomplete

## Deduplication

Alerts use the existing notification fingerprint logic. Duplicate alerts are still written to history as `DEDUPED` records, but no sender is invoked again for the same fingerprint within the dispatcher context.

## Safety

- Alerts are local-first.
- External senders remain optional injected transports.
- Alerts include `can_execute_trades: False`.
- No alert can trade, withdraw, sign, transfer, bridge, or access private keys.
