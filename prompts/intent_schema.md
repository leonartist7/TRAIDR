# Intent Schema

Return a strict JSON object with no extra fields:

```json
{
  "intent": "HOLD",
  "confidence": "unknown",
  "reason_codes": ["REASON_CODE"],
  "evidence_summary": ["short safe summary"],
  "risk_handoff_required": true,
  "requested_notional_usd": "10"
}
```

Allowed `intent` values are `HOLD`, `BUY`, `SELL`, and `INSUFFICIENT_DATA`.
Allowed `confidence` values are `low`, `medium`, `high`, and `unknown`.
`requested_notional_usd` is used only for bounded `BUY` or `SELL` research intents.

