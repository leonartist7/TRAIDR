"""Notification models for research-only alerts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Alert:
    subject_id: str
    state: str
    severity: AlertSeverity
    reason_codes: tuple[str, ...]
    message: str

    @property
    def fingerprint(self) -> str:
        material = "|".join((self.subject_id, self.state, self.severity.value, *self.reason_codes))
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "state": self.state,
            "severity": self.severity.value,
            "reason_codes": list(self.reason_codes),
            "message": self.message,
            "fingerprint": self.fingerprint,
            "can_execute_trades": False,
        }


@dataclass(frozen=True)
class SendResult:
    channel: str
    status: str
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
        }

