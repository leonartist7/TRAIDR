# Research Scheduler

TRAIDR's scheduler is a deterministic local research helper. It exposes callable task evaluation instead of a hidden background daemon.

## Default Intervals

- `watchlist_check`: 1 minute
- `technical_update`: 5 minutes
- `radar_update`: 15 minutes
- `macro_news_update`: 1 hour
- `opportunity_report`: 4 hours
- `daily_report`: 1 day

## Behavior

`ResearchScheduler.run_due_tasks()` accepts the current time, caller-supplied context, and last-run timestamps. It returns structured run results and can persist each run to DuckDB through `IntelligenceRepository`.

Missing handlers are safe: the scheduler records `SKIPPED` and does not create a background loop, network call, or execution action.

