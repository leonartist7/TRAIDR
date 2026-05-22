"""Logging helpers that scrub secret-like fields before emission."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

_SECRET_KEY_PARTS = (
    "api_key",
    "credential",
    "mnemonic",
    "password",
    "private_key",
    "seed",
    "secret",
    "token",
)
_REDACTED = "[REDACTED]"


def sanitize_log_fields(value: Any) -> Any:
    """Redact secret-like keys from structured logging fields."""

    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, field_value in value.items():
            key_text = str(key)
            if _is_secret_key(key_text):
                sanitized[key_text] = _REDACTED
            else:
                sanitized[key_text] = sanitize_log_fields(field_value)
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_log_fields(item) for item in value]
    return value


def get_logger(name: str) -> logging.Logger:
    """Return a project logger without configuring global logging."""

    normalized = name.strip(".")
    return logging.getLogger(f"traidr.{normalized}" if normalized else "traidr")


class SafeLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that redacts structured context before logging."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = kwargs.get("extra", {})
        kwargs["extra"] = sanitize_log_fields(extra)
        return msg, kwargs


def safe_adapter(logger: logging.Logger, **context: Any) -> SafeLoggerAdapter:
    """Attach sanitized structured context to a logger."""

    return SafeLoggerAdapter(logger, sanitize_log_fields(context))


def _is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return any(part in normalized for part in _SECRET_KEY_PARTS)

