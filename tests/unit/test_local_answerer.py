from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from ask.local_answerer import answer_local_question
from portfolio.repository import PortfolioRepository
from storage.duckdb_store import DuckDBStore
from storage.repositories import IntelligenceRepository, ResearchRepository
from storage.schema import initialize_schema


def test_local_answerer_missing_database_returns_setup_help(tmp_path: Path) -> None:
    answer = answer_local_question("show scan summary", database_path=tmp_path / "missing.duckdb")

    assert "No local DuckDB database found" in answer
    assert "can_execute_trades: false" in answer
    assert "scan --fixture" in answer


def test_local_answerer_answers_risk_alert_and_portfolio_questions(tmp_path: Path) -> None:
    database = tmp_path / "ask.duckdb"
    _seed_ask_database(database)

    risks = answer_local_question("what are my top risks?", database_path=database)
    alerts = answer_local_question("show recent alerts", database_path=database)
    portfolio = answer_local_question("portfolio summary", database_path=database)

    assert "Top Risks" in risks
    assert "fixture-sol-usdc" in risks
    assert "Recent Alerts" in alerts
    assert "WARNING" in alerts
    assert "Portfolio Summary" in portfolio
    assert "20.00" in portfolio


def test_local_answerer_unknown_question_returns_suggestions(tmp_path: Path) -> None:
    database = tmp_path / "ask-unknown.duckdb"
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)

    answer = answer_local_question("tell me something mysterious", database_path=database)

    assert "did not recognize" in answer
    assert "what are my top risks?" in answer


def _seed_ask_database(database: Path) -> None:
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        research = ResearchRepository(store.connection)
        intelligence = IntelligenceRepository(store.connection)
        research.record_evidence(
            source_name="market_scan:fixture",
            observed_at=now,
            quality_status="sufficient",
            payload={
                "pair_id": "fixture-sol-usdc",
                "source": "fixture",
                "can_execute_trades": False,
            },
            provenance={"source": "fixture", "can_execute_trades": False},
            collected_at=now,
        )
        intelligence.record_radar_state(
            subject_id="fixture-sol-usdc",
            state="AVOID",
            rank=1,
            opportunity_score=15.0,
            risk_score=90.0,
            confidence=0.9,
            reason_codes=("HIGH_RISK",),
            payload={"can_execute_trades": False},
            recorded_at=now,
        )
        intelligence.record_notification_alert(
            subject_id="fixture-sol-usdc",
            channel="local",
            severity="WARNING",
            fingerprint="risk-alert",
            status="RECORDED_ONLY",
            reason_codes=("HIGH_RISK",),
            payload={"can_execute_trades": False},
            recorded_at=now,
        )
        PortfolioRepository(store.connection).add_entry(
            symbol="SOL",
            chain="solana",
            pair_ref="solana/SOL",
            entry_price=Decimal("4.20"),
            size_usd=Decimal("20"),
            thesis="manual research",
            created_at=now,
        )
