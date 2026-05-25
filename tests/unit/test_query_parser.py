from ask.intents import AskIntent
from ask.query_parser import parse_question


def test_query_parser_maps_supported_questions() -> None:
    assert parse_question("what are my top risks?") is AskIntent.TOP_RISKS
    assert parse_question("show best radar candidates") is AskIntent.TOP_OPPORTUNITIES
    assert parse_question("what should I watch today?") is AskIntent.TOP_OPPORTUNITIES
    assert parse_question("show recent alerts") is AskIntent.RECENT_ALERTS
    assert parse_question("portfolio exposure please") is AskIntent.PORTFOLIO_SUMMARY
    assert parse_question("show safety status") is AskIntent.SAFETY_STATUS
    assert parse_question("scan summary") is AskIntent.SCAN_SUMMARY


def test_query_parser_unknown_question_fails_helpfully() -> None:
    assert parse_question("compose a poem about markets") is AskIntent.UNKNOWN_QUESTION
