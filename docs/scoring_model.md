# Scoring Model V2

Phase 36 adds a deterministic risk-adjusted scoring model for TRAIDR radar research.

## Inputs

- liquidity score
- volume score
- technical score
- safety score
- optional wallet score
- optional sentiment score
- optional macro score
- data quality score

## Outputs

- opportunity score
- risk score
- risk-adjusted score
- confidence
- reason codes
- human explanation
- `can_execute_trades: false`

## Safety Rules

- High rug or safety risk caps opportunity score.
- Missing critical safety data caps confidence.
- Low liquidity caps risk-adjusted score.
- Optional missing wallet, sentiment, or macro data never adds bullish weight.
- The model is deterministic and research-only.

The score cannot execute trades and does not alter the deterministic risk engine.
