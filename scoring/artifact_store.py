"""Local-only model artifact manifests with checksum and rollback metadata."""

from __future__ import annotations

import json
import pickle
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

from intelligence.production_models import ModelArtifactManifest, SignalDirection
from scoring.model_training import TrainedModelReport


def write_model_artifact(
    report: TrainedModelReport,
    *,
    model_id: str,
    version: str,
    direction: SignalDirection,
    horizon: Literal["5m", "15m", "1h", "4h", "1d"],
    feature_version: str,
    root: str | Path,
    rollback_artifact_id: str | None = None,
) -> ModelArtifactManifest:
    root_path = Path(root).resolve()
    root_path.mkdir(parents=True, exist_ok=True)
    artifact_path = (root_path / f"{model_id}-{version}.pkl").resolve()
    if artifact_path.parent != root_path:
        raise ValueError("model artifact path escaped configured directory")
    payload = pickle.dumps(report.model, protocol=5)
    digest = sha256(payload).hexdigest()
    artifact_path.write_bytes(payload)
    manifest = ModelArtifactManifest(
        artifact_id=f"artifact:{model_id}:{version}",
        model_id=model_id,
        version=version,
        direction=direction,
        horizon=horizon,
        role="champion" if report.promoted else "challenger",
        feature_schema=report.feature_names,
        training_start=report.training_start,
        training_end=report.training_end,
        metrics={
            "baseline_brier": report.baseline_brier,
            "challenger_brier": report.challenger_brier,
            "champion_brier": report.champion_brier,
            "calibration_error": report.champion_ece,
            "net_return_after_costs": report.net_return_after_costs,
            "maximum_drawdown": report.maximum_drawdown,
            "regime_stability": report.regime_stability,
        },
        artifact_path=str(artifact_path),
        sha256=digest,
        rollback_artifact_id=rollback_artifact_id,
        active=report.promoted,
        created_at=datetime.now(tz=UTC),
        reason_codes=report.reason_codes,
    )
    manifest_path = artifact_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest.model_dump(mode="json"), sort_keys=True, indent=2), encoding="utf-8")
    return manifest


def verify_model_artifact(manifest: ModelArtifactManifest, *, root: str | Path) -> bool:
    root_path = Path(root).resolve()
    artifact_path = Path(manifest.artifact_path).resolve()
    if artifact_path.parent != root_path or not artifact_path.is_file():
        return False
    return sha256(artifact_path.read_bytes()).hexdigest() == manifest.sha256
