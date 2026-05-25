from intelligence.macro_sources import fetch_macro_result, fixture_macro_result


def test_fixture_macro_works_offline() -> None:
    result = fixture_macro_result()

    assert result.status == "OK"
    assert result.can_execute_trades is False
    assert "classification" in result.score


def test_macro_source_parses_fear_greed_payload() -> None:
    result = fetch_macro_result(lambda: {"data": [{"value": "25"}]})

    assert result.status == "OK"
    assert result.signals["fear_greed"] == 0.25
    assert result.score["classification"] == "RISK_OFF"


def test_macro_network_failure_returns_insufficient_data() -> None:
    result = fetch_macro_result(lambda: (_ for _ in ()).throw(RuntimeError("offline")))

    assert result.status == "INSUFFICIENT_DATA"
    assert "MACRO_SOURCE_FETCH_FAILED" in result.reason_codes
