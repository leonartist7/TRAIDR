# Market Intelligence

TRAIDR's personal market intelligence layer is local, deterministic, and recommendation-only. It turns fixture or caller-supplied market context into structured analyses, CIO recommendations, radar states, alerts, scheduler runs, and reports stored in DuckDB.

## Boundaries

- Agents and radar modules can recommend `WATCH`, `ALERT`, `BUY_CANDIDATE`, `SELL_CANDIDATE`, or `AVOID`.
- No market intelligence module can execute trades or call the simulation broker.
- Missing critical data reduces confidence and can produce alert or insufficient-data outcomes.
- High-risk signals override opportunity scores.
- Stored payloads use the same safe JSON validation as earlier research and audit records.

## Storage

Schema version 2 adds append-only intelligence tables:

- `agent_analyses`
- `cio_decisions`
- `macro_news_events`
- `opportunity_radar_states`
- `notification_alerts`
- `scheduler_runs`
- `research_reports`

These tables are local research evidence. They are not order queues.

## Flow

1. Local macro, news, event, technical, liquidity, safety, and portfolio context is supplied.
2. Structured agents produce JSON-compatible analyses.
3. The CIO/ranker combines scores into a recommendation.
4. Opportunity radar ranks watchlist subjects.
5. Notification history records alert outcomes.
6. Scheduler ticks record deterministic task runs and reports.

