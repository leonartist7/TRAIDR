"""Shared fail-closed result types for TRAIDR."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, Iterable, TypeVar

T = TypeVar("T")


class ResultStatus(str, Enum):
    """Result states used before later phase-specific decision models exist."""

    OK = "OK"
    HOLD = "HOLD"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class Result(Generic[T]):
    """A small result object that keeps failure outcomes non-actionable."""

    status: ResultStatus
    value: T | None = None
    reason_codes: tuple[str, ...] = ()
    detail: str | None = None

    def __post_init__(self) -> None:
        normalized_reasons = tuple(self.reason_codes)
        object.__setattr__(self, "reason_codes", normalized_reasons)

        if self.status is ResultStatus.OK and normalized_reasons:
            raise ValueError("successful results cannot carry failure reason codes")
        if self.status is not ResultStatus.OK and self.value is not None:
            raise ValueError("non-actionable results cannot carry a value")
        if self.status is not ResultStatus.OK and not normalized_reasons:
            raise ValueError("non-actionable results require a reason code")
        if any(not reason.strip() for reason in normalized_reasons):
            raise ValueError("reason codes must be non-empty strings")

    @property
    def ok(self) -> bool:
        return self.status is ResultStatus.OK

    @property
    def actionable(self) -> bool:
        return self.ok

    @classmethod
    def success(cls, value: T | None = None) -> "Result[T]":
        return cls(status=ResultStatus.OK, value=value)

    @classmethod
    def hold(
        cls,
        *reason_codes: str,
        detail: str | None = None,
    ) -> "Result[T]":
        return cls._non_actionable(ResultStatus.HOLD, reason_codes, detail)

    @classmethod
    def insufficient_data(
        cls,
        *reason_codes: str,
        detail: str | None = None,
    ) -> "Result[T]":
        return cls._non_actionable(
            ResultStatus.INSUFFICIENT_DATA,
            reason_codes,
            detail,
        )

    @classmethod
    def rejected(
        cls,
        *reason_codes: str,
        detail: str | None = None,
    ) -> "Result[T]":
        return cls._non_actionable(ResultStatus.REJECTED, reason_codes, detail)

    @classmethod
    def _non_actionable(
        cls,
        status: ResultStatus,
        reason_codes: Iterable[str],
        detail: str | None,
    ) -> "Result[T]":
        return cls(
            status=status,
            reason_codes=tuple(reason_codes),
            detail=detail,
        )

