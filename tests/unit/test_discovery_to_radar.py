from data_pipeline.token_discovery import discover_tokens
from radar.discovery_to_radar import discovery_candidates_to_radar
from radar.models import OpportunityState


def test_discovery_candidates_convert_to_radar() -> None:
    result = discover_tokens(fixture=True)

    radar = discovery_candidates_to_radar(result.candidates)

    assert radar
    assert radar[0].to_dict()["can_execute_trades"] is False


def test_high_missing_discovery_data_is_not_buy_candidate() -> None:
    result = discover_tokens(fixture=True)
    partial = [candidate for candidate in result.candidates if candidate.missing_metric_count >= 2]

    radar = discovery_candidates_to_radar(partial)

    assert radar[0].state in {OpportunityState.WATCH, OpportunityState.ALERT, OpportunityState.AVOID}
    assert radar[0].state is not OpportunityState.BUY_CANDIDATE

