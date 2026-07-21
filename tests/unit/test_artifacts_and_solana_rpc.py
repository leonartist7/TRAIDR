import base64
from datetime import UTC, datetime, timedelta

from intelligence.production_models import SignalDirection
from onchain.solana_public_rpc import SolanaPublicRpcAdapter
from scoring.artifact_store import verify_model_artifact, write_model_artifact
from scoring.model_training import TrainedModelReport


NOW = datetime(2026, 7, 21, 12, tzinfo=UTC)


def test_model_artifact_manifest_detects_tampering(tmp_path) -> None:
    report = TrainedModelReport(
        champion_kind="logistic_regression",
        feature_names=("trend",),
        training_start=NOW - timedelta(days=30),
        training_end=NOW,
        training_samples=400,
        validation_samples=100,
        test_samples=100,
        baseline_brier=0.24,
        challenger_brier=0.22,
        champion_brier=0.20,
        champion_ece=0.04,
        net_return_after_costs=0.15,
        maximum_drawdown=2.0,
        regime_stability=0.9,
        promoted=True,
        reason_codes=("MODEL_PROMOTION_GATES_PASSED",),
        model={"deterministic_fixture": True},
    )
    manifest = write_model_artifact(
        report,
        model_id="directional-long-5m",
        version="test-v1",
        direction=SignalDirection.LONG,
        horizon="5m",
        feature_version="test",
        root=tmp_path,
    )

    assert verify_model_artifact(manifest, root=tmp_path)
    artifact = tmp_path / "directional-long-5m-test-v1.pkl"
    artifact.write_bytes(artifact.read_bytes() + b"tampered")
    assert not verify_model_artifact(manifest, root=tmp_path)


def test_solana_public_rpc_parses_mint_authorities_and_holder_concentration() -> None:
    raw = bytearray(82)
    raw[0:4] = (1).to_bytes(4, "little")
    raw[36:44] = (1_000_000).to_bytes(8, "little")
    raw[44] = 6
    raw[45] = 1
    raw[46:50] = (1).to_bytes(4, "little")

    def transport(method, _params):
        if method == "getAccountInfo":
            return {"result": {"value": {"data": [base64.b64encode(raw).decode(), "base64"]}}}
        return {"result": {"value": [{"amount": "850000"}, {"amount": "150000"}]}}

    evidence = SolanaPublicRpcAdapter(transport).fetch_mint_evidence("A" * 44)

    assert evidence is not None
    assert evidence.mint_authority_present
    assert evidence.freeze_authority_present
    assert evidence.largest_holder_fraction == 0.85
    assert evidence.safety_observation().unsafe_holder_or_creator_control is True
