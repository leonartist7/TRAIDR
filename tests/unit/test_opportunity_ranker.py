from agents.opportunity_ranker import rank_opportunity


def test_opportunity_ranker_detects_conflicting_agents() -> None:
    ranking = rank_opportunity(
        [
            {"agent": "technical", "score": 90, "risk_score": 10, "confidence": 0.8, "status": "OK"},
            {"agent": "token_safety", "score": 0, "risk_score": 95, "confidence": 0.9, "status": "HIGH_RISK"},
        ]
    )

    assert ranking.conflict_detected is True
    assert ranking.risk_score == 95
    assert "AGENT_CONFLICT_DETECTED" in ranking.reason_codes


def test_opportunity_ranker_missing_data_reduces_confidence() -> None:
    ranking = rank_opportunity(
        [
            {"agent": "technical", "score": 70, "risk_score": 20, "confidence": 0.8, "status": "OK"},
            {
                "agent": "liquidity",
                "score": 0,
                "risk_score": 50,
                "confidence": 0.0,
                "status": "INSUFFICIENT_DATA",
            },
        ]
    )

    assert ranking.missing_critical_count == 1
    assert ranking.confidence == 0.25
    assert "CRITICAL_DATA_MISSING" in ranking.reason_codes
