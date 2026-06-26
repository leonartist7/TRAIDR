"""Presentation view models for the TRAIDR Streamlit command center."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dashboard.queries import DashboardData


MissionState = Literal["complete", "ready", "missing"]


@dataclass(frozen=True)
class MissionItem:
    """A compact daily operator task shown in the cockpit."""

    label: str
    detail: str
    state: MissionState


@dataclass(frozen=True)
class CommandCard:
    """A safe allowlisted local workflow action."""

    label: str
    action: str
    button_label: str
    description: str
    detail: str
    accent: Literal["cyan", "green", "red", "blue"]


@dataclass(frozen=True)
class DashboardHealth:
    """Top-bar health state for the local dashboard."""

    database_label: str
    database_detail: str
    table_count: int
    radar_count: int
    alert_count: int
    portfolio_count: int
    report_count: int


def build_dashboard_health(data: DashboardData) -> DashboardHealth:
    """Summarize current local storage state for the header."""

    return DashboardHealth(
        database_label="Connected" if data.database_exists else "Missing",
        database_detail=str(data.database_path),
        table_count=len(data.tables),
        radar_count=len(data.market_radar),
        alert_count=len(data.alerts),
        portfolio_count=len(data.portfolio_entries),
        report_count=len(data.reports),
    )


def build_daily_mission(data: DashboardData) -> tuple[MissionItem, ...]:
    """Build the cockpit mission checklist from loaded dashboard data."""

    has_database = data.database_exists
    has_radar = bool(data.market_radar or data.scan_evidence)
    has_alerts = bool(data.alerts)
    has_portfolio = bool(data.portfolio_entries)
    has_reports = bool(data.reports)
    return (
        MissionItem(
            label="Refresh public market data",
            detail="Use the Bitunix refresh button for live read-only candles.",
            state="ready",
        ),
        MissionItem(
            label="Run daily workflow",
            detail="Creates local scan, radar, alert, and report evidence.",
            state="complete" if has_reports else ("ready" if has_database else "missing"),
        ),
        MissionItem(
            label="Review radar changes",
            detail="Check the highest-risk rows before opportunity rows.",
            state="complete" if has_radar else "ready",
        ),
        MissionItem(
            label="Read local alerts",
            detail="Alerts are local research notes and cannot trade.",
            state="complete" if has_alerts else "ready",
        ),
        MissionItem(
            label="Monitor manual portfolio",
            detail="Sell-risk is advisory only; no wallet or exchange connection.",
            state="complete" if has_portfolio else "ready",
        ),
    )


def build_command_cards() -> tuple[CommandCard, ...]:
    """Return the dashboard actions in a product-friendly order."""

    return (
        CommandCard(
            label="Run Daily Workflow",
            action="daily_run",
            button_label="Run",
            description="Full local research pipeline.",
            detail="Scan fixtures, update radar, generate alerts, save a report.",
            accent="cyan",
        ),
        CommandCard(
            label="Fixture Scan",
            action="fixture_scan",
            button_label="Scan",
            description="Offline market scan.",
            detail="Creates deterministic scan evidence without internet.",
            accent="blue",
        ),
        CommandCard(
            label="Paper Simulation",
            action="paper_simulation",
            button_label="Simulate",
            description="Risk-gated paper fill.",
            detail="Uses the deterministic risk engine before simulation.",
            accent="green",
        ),
        CommandCard(
            label="Generate Alerts",
            action="alerts_test",
            button_label="Generate",
            description="Local alert rule test.",
            detail="Stores deduped research alerts in DuckDB.",
            accent="red",
        ),
        CommandCard(
            label="Scheduler Once",
            action="scheduler_once",
            button_label="Run",
            description="One-shot scheduler.",
            detail="Runs due research tasks without a background daemon.",
            accent="blue",
        ),
        CommandCard(
            label="Inspect DB",
            action="status",
            button_label="Open",
            description="Local safety/storage status.",
            detail="Shows database and mode state. No shell execution.",
            accent="cyan",
        ),
    )


def summarize_action_output(output: str, *, max_lines: int = 6) -> tuple[str, ...]:
    """Extract high-signal lines from a command result for UI cards."""

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    important = [
        line
        for line in lines
        if any(
            marker in line.lower()
            for marker in (
                "status:",
                "mode:",
                "database:",
                "risk:",
                "execution:",
                "alerts_created:",
                "tasks_run:",
                "can_execute_trades:",
                "tables:",
            )
        )
    ]
    return tuple((important or lines)[:max_lines])
