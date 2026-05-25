# Trade Thesis Generator

Phase 38 adds structured research thesis notes for radar candidates.

The thesis generator does not execute trades and does not provide financial advice. It produces local research notes only.

## Output Fields

- `thesis_summary`
- `opportunity_drivers`
- `risk_factors`
- `invalidation_conditions`
- `watch_conditions`
- `exit_warning_conditions`
- `confidence`
- `data_gaps`
- `can_execute_trades: false`

## Rules

- Missing data is stated clearly in the thesis summary and data gaps.
- Risk factors are always present.
- Invalidation conditions are always present.
- Exit warning conditions are research-only and never create orders.
- Output is deterministic and local.

## Safety Boundary

The generator does not call brokers, exchanges, wallets, LLM providers, or network APIs. It is a documentation and research layer over existing radar/scoring evidence.
