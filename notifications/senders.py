"""Optional notification senders with injected transports only."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from notifications.models import Alert, SendResult
from utils.toon import assert_safe_payload

Transport = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class LocalOnlySender:
    channel = "local"

    def send(self, alert: Alert) -> SendResult:
        assert_safe_payload(alert.to_dict())
        return SendResult(self.channel, "RECORDED_ONLY", ("LOCAL_HISTORY_ONLY",))


class InjectedTransportSender:
    def __init__(self, channel: str, transport: Transport | None = None) -> None:
        self.channel = channel
        self.transport = transport

    def send(self, alert: Alert) -> SendResult:
        payload = {"channel": self.channel, "alert": alert.to_dict()}
        assert_safe_payload(payload)
        if self.transport is None:
            return SendResult(self.channel, "SKIPPED", ("TRANSPORT_NOT_CONFIGURED",))
        try:
            self.transport(payload)
        except Exception:
            return SendResult(self.channel, "FAILED", ("TRANSPORT_FAILED",))
        return SendResult(self.channel, "SENT", ("TRANSPORT_SENT",))


def ntfy_sender(transport: Transport | None = None) -> InjectedTransportSender:
    return InjectedTransportSender("ntfy", transport)


def telegram_sender(transport: Transport | None = None) -> InjectedTransportSender:
    return InjectedTransportSender("telegram", transport)


def discord_sender(transport: Transport | None = None) -> InjectedTransportSender:
    return InjectedTransportSender("discord", transport)

