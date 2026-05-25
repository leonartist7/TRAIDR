"""Terminal formatters for read-only reports."""

from __future__ import annotations

from cli.formatters import bullet_list, key_values, records_table, section
from reports.report_models import DailyBriefing


def format_daily_briefing(briefing: DailyBriefing) -> str:
    blocks = [
        section(
            "Daily Briefing",
            key_values(
                {
                    "state": briefing.state.value,
                    "generated_at": briefing.generated_at.isoformat(),
                    "can_execute_trades": briefing.can_execute_trades,
                    "reason_codes": briefing.reason_codes,
                }
            ).splitlines(),
        ),
        section("Market Scan Summary", key_values(briefing.market_scan_summary).splitlines()),
        section(
            "Top Radar Candidates",
            records_table(briefing.top_radar_candidates, empty="No radar candidates found.").splitlines(),
        ),
        section(
            "Highest Risk Candidates",
            records_table(briefing.highest_risk_candidates, empty="No risk-ranked candidates found.").splitlines(),
        ),
        section(
            "New Alerts",
            records_table(briefing.new_alerts, empty="No new local alerts found.").splitlines(),
        ),
        section(
            "Recent Simulation Results",
            records_table(briefing.recent_simulation_results, empty="No recent paper simulation results found.").splitlines(),
        ),
        section("Current Safety Status", key_values(briefing.current_safety_status).splitlines()),
        section("Missing Data Warnings", bullet_list(briefing.missing_data_warnings).splitlines()),
        section("Suggested Watchlist", bullet_list(briefing.suggested_watchlist).splitlines()),
        section("No Execution Actions", ["This briefing is read-only research and cannot execute trades."]),
    ]
    if briefing.next_commands:
        blocks.append(section("Next Commands", bullet_list(briefing.next_commands).splitlines()))
    return "\n\n".join(blocks)
