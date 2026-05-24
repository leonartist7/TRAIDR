# Notifications

TRAIDR notifications are local alert records with optional injected outbound transports. They are not execution signals and do not contain custody, wallet, or secret material.

## Default Behavior

The default sender is local-only. It records alert history in DuckDB and reports `RECORDED_ONLY`.

## Optional Senders

Optional ntfy, Telegram, and Discord senders use injected transport callables. TRAIDR does not require API keys for tests and does not store notification tokens. Tests use mocks only.

If no transport is configured, optional senders return `SKIPPED` with `TRANSPORT_NOT_CONFIGURED`.

## Deduplication

Alerts are deduplicated by a fingerprint built from:

- subject id
- opportunity state
- severity
- reason codes

Repeated fingerprints are recorded as `DEDUPED`.

