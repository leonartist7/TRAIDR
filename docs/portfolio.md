# Manual Portfolio Tracker

TRAIDR manual portfolio tracking is local personal analysis. It does not connect to exchanges or wallets and cannot execute trades.

## Commands

```powershell
python -m cli.main portfolio add BONK --entry 0.001 --size-usd 20 --thesis "meme momentum"
python -m cli.main portfolio list
python -m cli.main portfolio remove <entry_id>
python -m cli.main portfolio report
```

Optional fields:

```powershell
python -m cli.main portfolio add BONK --entry 0.001 --size-usd 20 --thesis "meme momentum" --chain solana --pair-ref solana/BONK --stop-zone "below support" --take-profit-zone "2x" --conviction medium --risk-level high --notes "manual note"
```

## Tracked Fields

- symbol
- chain
- pair reference
- entry price
- size in USD
- thesis
- stop zone
- take-profit zone
- conviction
- risk level
- notes

## Report Fields

- total exposure
- concentration risk
- meme exposure
- chain exposure
- thesis warnings
- stale thesis warnings
- no execution actions

## Safety

- No exchange connections.
- No wallet connections.
- No private-key handling.
- No live or simulated order execution.
- Manual entries always include `can_execute_trades: False`.
