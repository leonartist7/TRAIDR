from radar.models import OpportunityState
from radar.opportunity_radar import rank_watchlist
from radar.state_machine import classify_opportunity
from radar.watchlist import normalize_watchlist


def test_state_machine_high_risk_overrides_opportunity() -> None:
    state, reasons = classify_opportunity(
        opportunity_score=95,
        risk_score=80,
        confidence=0.9,
    )

    assert state is OpportunityState.AVOID
    assert "HIGH_RISK_OVERRIDES_OPPORTUNITY" in reasons


def test_rank_watchlist_orders_candidates_and_keeps_non_executable() -> None:
    ranked = rank_watchlist(
        [
            {
                "subject_id": "token-a",
                "analyses": [
                    {"agent": "technical", "score": 80, "risk_score": 20, "confidence": 0.8, "status": "OK"}
                ],
            },
            {
                "subject_id": "token-b",
                "analyses": [
                    {"agent": "safety", "score": 90, "risk_score": 90, "confidence": 0.9, "status": "OK"}
                ],
            },
        ]
    )

    assert ranked[0].subject_id == "token-a"
    assert ranked[0].state is OpportunityState.BUY_CANDIDATE
    assert ranked[0].to_dict()["can_execute_trades"] is False
    assert ranked[1].state is OpportunityState.AVOID


def test_rank_watchlist_missing_data_reduces_confidence_to_alert() -> None:
    ranked = rank_watchlist(
        [
            {
                "subject_id": "token-c",
                "analyses": [
                    {
                        "agent": "liquidity",
                        "score": 0,
                        "risk_score": 50,
                        "confidence": 0.0,
                        "status": "INSUFFICIENT_DATA",
                    }
                ],
            }
        ]
    )

    assert ranked[0].state is OpportunityState.ALERT
    assert "CRITICAL_DATA_MISSING" in ranked[0].reason_codes


def test_normalize_watchlist_drops_records_without_subject() -> None:
    normalized = normalize_watchlist([{"pair_id": "token-a"}, {"analyses": []}])

    assert len(normalized) == 1
    assert normalized[0]["subject_id"] == "token-a"
