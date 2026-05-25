from datetime import datetime, timezone
from decimal import Decimal

from alerts.rules import AlertRuleId, ResearchAlertSnapshot, evaluate_alert_rules
from alerts.rule_engine import ResearchAlertRuleEngine
from notifications.dedupe import AlertDeduper
from notifications.dispatcher import NotificationDispatcher
from notifications.history import AlertHistory
from storage.duckdb_store import DuckDBStore
from storage.repositories import IntelligenceRepository
from storage.schema import initialize_schema

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_alert_rules_cover_score_liquidity_state_stale_and_safety_changes() -> None:
    previous = ResearchAlertSnapshot(
        subject_id="fixture-sol-usdc",
        state="ALERT",
        opportunity_score=40.0,
        risk_score=10.0,
        liquidity_usd=Decimal("10000"),
    )
    current = ResearchAlertSnapshot(
        subject_id="fixture-sol-usdc",
        state="BUY_CANDIDATE",
        opportunity_score=60.0,
        risk_score=30.0,
        liquidity_usd=Decimal("7000"),
        data_quality="stale",
        safety_complete=False,
    )

    matches = evaluate_alert_rules(previous, current)
    ids = {match.rule_id for match in matches}

    assert AlertRuleId.OPPORTUNITY_INCREASED in ids
    assert AlertRuleId.RISK_INCREASED in ids
    assert AlertRuleId.LIQUIDITY_DROPPED in ids
    assert AlertRuleId.ALERT_TO_BUY_CANDIDATE in ids
    assert AlertRuleId.SCAN_DATA_STALE in ids
    assert AlertRuleId.SAFETY_DATA_INCOMPLETE in ids
    assert all(match.can_execute_trades is False for match in matches)


def test_alert_rules_detect_liquidity_increase_watch_to_alert_and_avoid() -> None:
    watch = ResearchAlertSnapshot(
        subject_id="fixture-sol-usdc",
        state="WATCH",
        opportunity_score=40.0,
        risk_score=20.0,
        liquidity_usd=Decimal("1000"),
    )
    alert = ResearchAlertSnapshot(
        subject_id="fixture-sol-usdc",
        state="ALERT",
        opportunity_score=42.0,
        risk_score=20.0,
        liquidity_usd=Decimal("1300"),
    )
    avoid = ResearchAlertSnapshot(
        subject_id="fixture-sol-usdc",
        state="AVOID",
        opportunity_score=5.0,
        risk_score=90.0,
        liquidity_usd=Decimal("1300"),
    )

    first_ids = {match.rule_id for match in evaluate_alert_rules(watch, alert)}
    second_ids = {match.rule_id for match in evaluate_alert_rules(alert, avoid)}

    assert AlertRuleId.LIQUIDITY_INCREASED in first_ids
    assert AlertRuleId.WATCH_TO_ALERT in first_ids
    assert AlertRuleId.MOVED_TO_AVOID in second_ids


def test_rule_engine_dispatches_and_dedupes_local_alerts() -> None:
    previous = ResearchAlertSnapshot(
        subject_id="fixture-sol-usdc",
        state="WATCH",
        opportunity_score=40.0,
        risk_score=20.0,
        liquidity_usd=Decimal("10000"),
    )
    current = ResearchAlertSnapshot(
        subject_id="fixture-sol-usdc",
        state="ALERT",
        opportunity_score=60.0,
        risk_score=20.0,
        liquidity_usd=Decimal("10000"),
    )

    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        history = AlertHistory(IntelligenceRepository(store.connection))
        engine = ResearchAlertRuleEngine(
            NotificationDispatcher(history=history, deduper=AlertDeduper())
        )
        first = engine.evaluate_and_dispatch(previous=previous, current=current, now=NOW)
        second = engine.evaluate_and_dispatch(previous=previous, current=current, now=NOW)
        rows = store.connection.execute("SELECT status, payload_json FROM notification_alerts").fetchall()

    assert first.alerts_created == 2
    assert second.alerts_created == 0
    assert any(row[0] == "DEDUPED" for row in rows)
    assert all('"can_execute_trades":false' in row[1] for row in rows)
