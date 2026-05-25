# Sentiment Lite

Phase 32 adds local sentiment feature extraction from provided text snippets. It is fixture-first and local by default.

## Scope

Sentiment lite detects:

- positive momentum language
- negative warning language
- scam or rug language
- repeated spam/shill patterns
- ticker mentions

The scorer returns a conservative sentiment score, confidence, reason codes, and `can_execute_trades: false`.

## Safety Behavior

- Missing sentiment is `INSUFFICIENT_DATA`.
- Spam reduces confidence.
- Scam language reduces confidence and score.
- Sentiment can inform narrative/radar confidence only.
- No scraping private groups.
- No automated posting.
- No sentiment manipulation.
- No execution actions.

## Usage

The feature extractor is currently a module boundary used by narrative and radar components:

```python
from sentiment.scorer import score_sentiment_snippets

score = score_sentiment_snippets(["$TOKEN breakout momentum", "warning: liquidity drain"])
```

Future source adapters must remain optional, mockable, and read-only.
