import pytest

from utils.results import Result, ResultStatus


def test_result_success_is_actionable() -> None:
    result = Result.success({"mode": "simulation"})

    assert result.ok is True
    assert result.actionable is True
    assert result.status is ResultStatus.OK
    assert result.value == {"mode": "simulation"}


def test_insufficient_data_result_is_non_actionable() -> None:
    result = Result.insufficient_data("TIMESTAMP_STALE")

    assert result.ok is False
    assert result.actionable is False
    assert result.status is ResultStatus.INSUFFICIENT_DATA
    assert result.reason_codes == ("TIMESTAMP_STALE",)
    assert result.value is None


def test_non_actionable_result_requires_reason_code() -> None:
    with pytest.raises(ValueError):
        Result(status=ResultStatus.HOLD)

