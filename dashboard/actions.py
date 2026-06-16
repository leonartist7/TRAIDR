"""Safe dashboard-triggered local actions for TRAIDR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cli import commands


@dataclass(frozen=True)
class DashboardActionResult:
    """Result from a dashboard button action."""

    label: str
    exit_code: int
    output: str
    can_execute_trades: bool = False


def run_dashboard_action(action: str, *, database: str) -> DashboardActionResult:
    """Run an allowlisted local action from the dashboard.

    These actions intentionally reuse CLI command functions directly instead of
    spawning a shell. They remain simulation/read-only research actions.
    """

    actions: dict[str, tuple[str, Callable[[], commands.CommandResult]]] = {
        "status": ("Status Check", lambda: commands.status(database)),
        "daily_run": ("Daily Run", lambda: commands.daily_run(database)),
        "fixture_scan": ("Fixture Scan", lambda: commands.scan(database=database, fixture=True)),
        "fixture_radar": ("Fixture Radar", lambda: commands.radar(database=database, fixture=True)),
        "briefing": ("Daily Briefing", lambda: commands.briefing(database)),
        "alerts": ("Alert History", lambda: commands.alerts(database)),
        "alerts_test": ("Generate Test Alerts", lambda: commands.alerts_test(database)),
        "scheduler_once": ("Scheduler Once", lambda: commands.scheduler_once(database)),
        "paper_simulation": ("Paper Simulation", lambda: commands.simulate(database)),
    }
    if action not in actions:
        return DashboardActionResult(
            label="Unknown Action",
            exit_code=2,
            output="Unsupported dashboard action. No action was run.",
        )
    label, runner = actions[action]
    result = runner()
    return DashboardActionResult(
        label=label,
        exit_code=result.exit_code,
        output=result.output,
    )
