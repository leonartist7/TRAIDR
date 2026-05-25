"""Supported local Ask TRAIDR intents."""

from __future__ import annotations

from enum import StrEnum


class AskIntent(StrEnum):
    TOP_RISKS = "top_risks"
    TOP_OPPORTUNITIES = "top_opportunities"
    RECENT_ALERTS = "recent_alerts"
    PORTFOLIO_SUMMARY = "portfolio_summary"
    SAFETY_STATUS = "safety_status"
    SCAN_SUMMARY = "scan_summary"
    UNKNOWN_QUESTION = "unknown_question"


SUGGESTED_QUESTIONS = (
    "what are my top risks?",
    "show best radar candidates",
    "what should I watch today?",
    "show recent alerts",
    "show portfolio summary",
    "show safety status",
    "show scan summary",
)
