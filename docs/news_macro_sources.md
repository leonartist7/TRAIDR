# News And Macro Sources

Phase 31 adds read-only macro and news adapters for local market intelligence. These adapters affect research confidence only; they cannot execute trades, create orders, access wallets, or handle private keys.

## Commands

Offline fixture mode:

```bash
python -m cli.main news --fixture
python -m cli.main macro --fixture
```

Optional read-only RSS mode:

```bash
python -m cli.main news --source rss
python -m cli.main news --source rss --url https://example.com/feed.xml
```

Optional read-only macro mode:

```bash
python -m cli.main macro
```

## Safety Behavior

- Missing news is `INSUFFICIENT_DATA`, never bullish.
- RSS/network failures return `INSUFFICIENT_DATA`.
- Macro source failures return `INSUFFICIENT_DATA`.
- No paid APIs or API keys are required.
- Tests use fixture or mocked transports only.
- Output includes `can_execute_trades: false`.

## Detected News Categories

- `HACK_EXPLOIT_RISK`
- `LISTING_NEWS`
- `DELISTING_RISK`
- `REGULATION_RISK`
- `PARTNERSHIP_PRODUCT_NEWS`
- `MARKET_WIDE_RISK_OFF`

These reason codes may change opportunity confidence, but they do not bypass the deterministic risk engine and do not call any execution module.
