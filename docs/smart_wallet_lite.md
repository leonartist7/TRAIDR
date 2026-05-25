# Smart Wallet Lite

Phase 33 converts fixture wallet histories and wallet graph cluster evidence into local smart-money research signals.

## Scope

Smart wallet lite scores:

- repeated early entries
- win/loss ratio when known
- rug avoidance when known
- cyclic transfer risk from wallet graph analysis
- shared funder risk from wallet graph analysis
- developer-link risk

Smart wallet score is separate from token safety score. It is research evidence, not permission to trade.

## Safety Behavior

- Unknown wallet history is not bullish.
- Incomplete evidence returns no smart wallet score.
- Cluster risk reduces confidence/score.
- Developer-link risk is penalized.
- No paid APIs are required.
- No live RPC calls are required.
- No wallet connections or private keys.
- No execution actions.

## Fixture Usage

```python
from onchain.wallet_profiles import build_wallet_profile
from onchain.smart_wallet_score import score_smart_wallet

profile = build_wallet_profile({"wallet": "wallet-a", "developer_link_risk": False, "trades": []})
score = score_smart_wallet(profile)
```

All outputs include `can_execute_trades: false` when serialized.
