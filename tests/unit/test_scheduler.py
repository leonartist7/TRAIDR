from datetime import timedelta

from scheduler.reports import build_research_report
from scheduler.research_scheduler import ResearchScheduler


def test_scheduler_detects_due_tasks(now) -> None:
    scheduler = ResearchScheduler()
    due = scheduler.due_tasks(
        now=now,
        last_runs={"watchlist_check": now - timedelta(seconds=30), "technical_update": now - timedelta(minutes=6)},
    )

    assert [task.name for task in due] == [
        "technical_update",
        "radar_update",
        "macro_news_update",
        "opportunity_report",
        "daily_report",
    ]


def test_scheduler_run_due_tasks_uses_handler(now) -> None:
    scheduler = ResearchScheduler(
        handlers={"watchlist_check": lambda context: {"status": "OK", "reason_codes": ["WATCHLIST_CHECKED"]}}
    )

    results = scheduler.run_due_tasks(
        now=now,
        context={},
        last_runs={task.name: now for task in scheduler.tasks if task.name != "watchlist_check"},
    )

    assert len(results) == 1
    assert results[0].status == "OK"
    assert results[0].to_dict()["can_execute_trades"] is False


def test_research_report_summarizes_radar_states() -> None:
    report = build_research_report(
        report_type="opportunity",
        radar_states=[
            {"subject_id": "a", "state": "BUY_CANDIDATE"},
            {"subject_id": "b", "state": "AVOID"},
        ],
    )

    assert report["candidate_count"] == 1
    assert report["high_risk_count"] == 1
    assert report["can_execute_trades"] is False

