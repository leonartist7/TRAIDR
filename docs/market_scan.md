# Market Scan

TRAIDR market scan mode is read-only research. It normalizes market data through existing safe adapter boundaries, maps scan candidates into the opportunity radar, and can store scan evidence in local DuckDB.

## Commands

Offline fixture scan:

```powershell
python -m cli.main scan --fixture
```

Persist fixture scan evidence:

```powershell
python -m cli.main scan --fixture --database storage/duckdb/traidr_test.duckdb
```

Optional real-source scan requires explicit pair references and configured/injected adapter paths. If no source can provide data, TRAIDR returns `INSUFFICIENT_DATA` and prints a clean no-candidates message.

```powershell
python -m cli.main scan --pair-ref solana:example
```

## Output Fields

Every scan candidate includes:

- token/pair id
- source
- observed timestamp
- price, liquidity, and 24h volume when available
- data-quality status
- reason codes
- `can_execute_trades: False`

## Safety

- Scan mode never executes trades.
- Scan mode never handles withdrawals.
- Scan mode never handles private keys or wallet signing.
- Real-source failures never fabricate bullish data.
- Missing or failed data returns `INSUFFICIENT_DATA`.
