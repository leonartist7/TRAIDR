# Token Discovery

TRAIDR token discovery is read-only research. It finds candidate pairs from fixture data or the public DexScreener token-profile feed and converts those candidates into conservative radar output.

## Commands

Offline fixture discovery:

```powershell
python -m cli.main discover --fixture
```

Persist fixture discovery evidence:

```powershell
python -m cli.main discover --fixture --database storage/duckdb/traidr_discovery.duckdb
```

Read-only DexScreener discovery:

```powershell
python -m cli.main discover --source dexscreener --limit 20
python -m cli.main discover --source dexscreener --database storage/duckdb/traidr_discovery.duckdb
```

DexScreener discovery uses the public latest token profiles endpoint. These records can be sparse, so missing price, liquidity, or volume is carried forward as missing data and lowers radar confidence. If the public source is unavailable, malformed, or empty, TRAIDR returns `INSUFFICIENT_DATA` and does not invent candidates.

## Output Fields

Each discovery candidate includes:

- `pair_id`
- `chain`
- `base_symbol`
- `quote_symbol`
- `price_usd`
- `liquidity_usd`
- `volume_24h_usd`
- `source`
- `observed_at`
- `reason_codes`
- `can_execute_trades: False`

## Safety

- Discovery results are research-only.
- Discovered tokens cannot execute trades.
- Missing data reduces radar confidence.
- High missing data becomes `WATCH`, `ALERT`, or `AVOID`, never `BUY_CANDIDATE`.
- No live trading, withdrawals, wallet signing, or private-key handling is introduced.
