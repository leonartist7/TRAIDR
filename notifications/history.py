"""DuckDB-backed local alert history."""

from __future__ import annotations

from datetime import datetime

from notifications.models import Alert, SendResult
from storage.repositories import IntelligenceRepository


class AlertHistory:
    def __init__(self, repository: IntelligenceRepository) -> None:
        self.repository = repository

    def record(
        self,
        alert: Alert,
        result: SendResult,
        *,
        recorded_at: datetime | None = None,
    ) -> str:
        return self.repository.record_notification_alert(
            subject_id=alert.subject_id,
            channel=result.channel,
            severity=alert.severity.value,
            fingerprint=alert.fingerprint,
            status=result.status,
            reason_codes=(*alert.reason_codes, *result.reason_codes),
            payload={"alert": alert.to_dict(), "send_result": result.to_dict()},
            recorded_at=recorded_at,
        )

