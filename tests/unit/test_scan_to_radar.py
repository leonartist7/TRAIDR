from dataclasses import replace

from data_pipeline.market_scan import scan_markets
from radar.models import OpportunityState
from radar.scan_to_radar import scan_candidates_to_radar


def test_scan_candidates_feed_existing_radar() -> None:
    scan = scan_markets(fixture=True)

    radar = scan_candidates_to_radar(scan.candidates)

    assert radar
    assert radar[0].subject_id == "fixture-sol-usdc"
    assert radar[0].to_dict()["can_execute_trades"] is False


def test_insufficient_scan_candidate_is_not_bullish() -> None:
    scan = scan_markets(fixture=True)
    bad_candidate = replace(
        scan.candidates[0],
        data_quality="missing",
        snapshot=None,
        reason_codes=("SCAN_CANDIDATE_INSUFFICIENT_DATA",),
    )

    radar = scan_candidates_to_radar([bad_candidate])

    assert radar[0].state is OpportunityState.AVOID
    assert "CRITICAL_DATA_MISSING" in radar[0].reason_codes
