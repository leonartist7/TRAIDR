from notifications.dedupe import AlertDeduper
from notifications.dispatcher import NotificationDispatcher
from notifications.history import AlertHistory
from notifications.models import Alert, AlertSeverity
from notifications.senders import LocalOnlySender, discord_sender, ntfy_sender, telegram_sender
from storage.repositories import IntelligenceRepository


def test_alert_dedupe_blocks_repeat_fingerprint() -> None:
    alert = Alert("token-a", "BUY_CANDIDATE", AlertSeverity.WARNING, ("RESEARCH_ONLY",), "Watch token-a")
    deduper = AlertDeduper()

    assert deduper.should_send(alert) is True
    assert deduper.should_send(alert) is False


def test_local_sender_records_only() -> None:
    alert = Alert("token-a", "WATCH", AlertSeverity.INFO, ("WATCHLIST_MONITORING",), "Watch token-a")

    result = LocalOnlySender().send(alert)

    assert result.status == "RECORDED_ONLY"


def test_optional_sender_uses_injected_transport_only() -> None:
    calls = []
    sender = discord_sender(lambda payload: calls.append(payload) or {"ok": True})
    alert = Alert("token-a", "ALERT", AlertSeverity.WARNING, ("LOCAL_TEST",), "Alert token-a")

    result = sender.send(alert)

    assert result.status == "SENT"
    assert calls[0]["channel"] == "discord"


def test_optional_senders_skip_without_transport() -> None:
    alert = Alert("token-a", "WATCH", AlertSeverity.INFO, ("LOCAL_TEST",), "Watch token-a")

    assert ntfy_sender().send(alert).status == "SKIPPED"
    assert telegram_sender().send(alert).status == "SKIPPED"


def test_dispatcher_records_local_history(duckdb_store, now) -> None:
    repository = IntelligenceRepository(duckdb_store.connection)
    dispatcher = NotificationDispatcher(history=AlertHistory(repository))
    alert = Alert("token-a", "ALERT", AlertSeverity.WARNING, ("LOCAL_TEST",), "Alert token-a")

    results = dispatcher.dispatch(alert, now=now)

    count = duckdb_store.connection.execute("SELECT COUNT(*) FROM notification_alerts").fetchone()[0]
    assert results[0].status == "RECORDED_ONLY"
    assert count == 1
