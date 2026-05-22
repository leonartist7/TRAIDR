"""Safe TOON serialization for scrubbed LLM payloads."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, TypeAlias

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | Mapping[str, "JsonValue"] | Sequence["JsonValue"]

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRET_KEY_PARTS = (
    "api_key",
    "credential",
    "mnemonic",
    "password",
    "private_key",
    "seed_phrase",
    "secret",
    "token",
)
_OBVIOUS_SECRET_VALUE_MARKERS = (
    "-----begin private key-----",
    "-----begin encrypted private key-----",
)


class ToonSerializationError(ValueError):
    """Raised when a payload cannot be safely serialized as TOON."""


class UnsafePayloadError(ToonSerializationError):
    """Raised when a payload may expose secret-bearing material."""


def serialize_toon(payload: Mapping[str, JsonValue]) -> str:
    """Serialize a safe JSON-like mapping into a small TOON subset."""

    if not isinstance(payload, Mapping):
        raise ToonSerializationError("TOON payload root must be a mapping")

    assert_safe_payload(payload)
    lines: list[str] = []
    _encode_mapping(payload, lines, indent=0)
    return "\n".join(lines)


def assert_safe_payload(payload: JsonValue) -> None:
    """Reject secret-like fields and unsupported values before LLM serialization."""

    _validate_value(payload, path=())


def _validate_value(value: JsonValue, path: tuple[str, ...]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ToonSerializationError("TOON mapping keys must be strings")
            if _is_secret_key(key):
                dotted_path = ".".join((*path, key))
                raise UnsafePayloadError(f"secret-like key is not serializable: {dotted_path}")
            _validate_value(child, (*path, key))
        return

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _validate_value(child, (*path, f"[{index}]"))
        return

    if isinstance(value, Decimal):
        raise ToonSerializationError("Decimal values must be normalized before TOON")
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        raise ToonSerializationError("non-finite floats are not serializable")
    if isinstance(value, str) and any(
        marker in value.lower() for marker in _OBVIOUS_SECRET_VALUE_MARKERS
    ):
        raise UnsafePayloadError("private key material is not serializable")
    if not isinstance(value, (str, int, float, bool, type(None))):
        raise ToonSerializationError(f"unsupported TOON value type: {type(value).__name__}")


def _encode_mapping(value: Mapping[str, JsonValue], lines: list[str], indent: int) -> None:
    for key, child in value.items():
        key_text = _encode_key(key)
        prefix = " " * indent
        if isinstance(child, Mapping):
            lines.append(f"{prefix}{key_text}:")
            _encode_mapping(child, lines, indent + 2)
        elif _is_primitive_sequence(child):
            rendered = ",".join(_encode_primitive(item) for item in child)
            lines.append(f"{prefix}{key_text}[{len(child)}]: {rendered}")
        elif _is_tabular_sequence(child):
            rows = list(child)
            fields = list(rows[0].keys())
            field_header = ",".join(_encode_key(field) for field in fields)
            lines.append(f"{prefix}{key_text}[{len(rows)}]{{{field_header}}}:")
            for row in rows:
                rendered = ",".join(_encode_primitive(row[field]) for field in fields)
                lines.append(f"{prefix}  {rendered}")
        elif _is_sequence(child):
            lines.append(f"{prefix}{key_text}[{len(child)}]:")
            _encode_list(child, lines, indent + 2)
        else:
            lines.append(f"{prefix}{key_text}: {_encode_primitive(child)}")


def _encode_list(value: Sequence[JsonValue], lines: list[str], indent: int) -> None:
    prefix = " " * indent
    for child in value:
        if isinstance(child, Mapping):
            child_items = list(child.items())
            if not child_items:
                lines.append(f"{prefix}- {{}}")
                continue
            first_key, first_value = child_items[0]
            if isinstance(first_value, Mapping) or _is_sequence(first_value):
                lines.append(f"{prefix}- {_encode_key(first_key)}:")
                _encode_nested_value(first_value, lines, indent + 4)
            else:
                lines.append(
                    f"{prefix}- {_encode_key(first_key)}: {_encode_primitive(first_value)}"
                )
            _encode_mapping(dict(child_items[1:]), lines, indent + 2)
        elif _is_sequence(child):
            lines.append(f"{prefix}- [{len(child)}]:")
            _encode_list(child, lines, indent + 2)
        else:
            lines.append(f"{prefix}- {_encode_primitive(child)}")


def _encode_nested_value(value: JsonValue, lines: list[str], indent: int) -> None:
    if isinstance(value, Mapping):
        _encode_mapping(value, lines, indent)
    elif _is_sequence(value):
        _encode_list(value, lines, indent)
    else:
        raise ToonSerializationError("nested TOON value is not a container")


def _encode_key(key: str) -> str:
    return key if _IDENTIFIER.fullmatch(key) else json.dumps(key, ensure_ascii=True)


def _encode_primitive(value: JsonPrimitive) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        if _needs_quotes(value):
            return json.dumps(value, ensure_ascii=True)
        return value
    return str(value)


def _needs_quotes(value: str) -> bool:
    if not value or value.strip() != value:
        return True
    if value.lower() in {"true", "false", "null"}:
        return True
    return any(character in value for character in (",", ":", "{", "}", "[", "]", "\n", '"'))


def _is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return any(part in normalized for part in _SECRET_KEY_PARTS)


def _is_sequence(value: JsonValue) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    )


def _is_primitive(value: JsonValue) -> bool:
    return isinstance(value, (str, int, float, bool, type(None)))


def _is_primitive_sequence(value: JsonValue) -> bool:
    return _is_sequence(value) and all(_is_primitive(item) for item in value)


def _is_tabular_sequence(value: JsonValue) -> bool:
    if not _is_sequence(value) or not value:
        return False
    if not all(isinstance(item, Mapping) and item for item in value):
        return False

    first_fields = tuple(value[0].keys())
    return all(
        tuple(item.keys()) == first_fields and all(_is_primitive(child) for child in item.values())
        for item in value
    )

