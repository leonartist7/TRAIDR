# Token Detail

TRAIDR token detail cards are local, read-only research reports for one token pair. They combine normalized market data, optional technical vectors, conservative radar scoring, and anti-rug evidence status without creating executable trade instructions.

## Commands

Offline fixture detail:

```powershell
python -m cli.main token --fixture
```

Read-only DexScreener pair detail:

```powershell
python -m cli.main token --pair-ref solana/PAIR_ADDRESS --source dexscreener
python -m cli.main token --pair-ref solana/PAIR_ADDRESS --source dexscreener --database storage/duckdb/traidr_token.duckdb
```

## Output

The detail card includes:

- token identity
- price, liquidity, and volume
- technical vector when local candles are available
- liquidity, opportunity, and risk scores
- anti-rug evidence status and unknown safety fields
- radar state and reason codes
- `can_execute_trades: False`
- plain-English why-interesting and why-risky summaries

## Safety

- Token detail is research-only.
- The command cannot execute trades.
- The command cannot withdraw, transfer, bridge, sign, or handle private keys.
- Real-source mode is read-only and fails closed when required market data is missing.
- Unknown anti-rug fields are shown as unknown instead of converted into bullish data.
