# Sell-Risk Monitor

TRAIDR sell-risk monitoring reviews manually entered positions against local scan, radar, macro/news, and thesis evidence. It does not execute trades.

## Commands

```powershell
python -m cli.main portfolio monitor
python -m cli.main portfolio sell-risk
```

Both commands read active manual portfolio entries and produce research-only sell-risk states.

## Output States

- `HOLD_POSITION`
- `REVIEW_POSITION`
- `REDUCE_RISK`
- `EXIT_CANDIDATE`
- `INSUFFICIENT_DATA`

## Signals

- liquidity drain
- risk score increased
- radar state changed to `AVOID`
- opportunity score collapsed
- token safety incomplete
- macro/news risk-off, when available
- thesis stale
- stop zone reached, when current price is known

## Safety

- No trade execution.
- No exchange connection.
- No wallet connection.
- No private-key handling.
- Sell-risk output includes `can_execute_trades: False`.
- `EXIT_CANDIDATE` is a research review state, not an order instruction.
