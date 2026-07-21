"""Typed local-only runtime profiles with forbidden modes absent by design."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from intelligence.production_models import DataMode

PROFILES_PATH = Path(__file__).with_name("research_profiles.yaml")
PROJECT_ROOT = PROFILES_PATH.parents[1]


class RuntimeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    data_mode: DataMode
    network_enabled: bool
    preview_watermark: bool

    @model_validator(mode="after")
    def _network_boundary(self) -> "RuntimeProfile":
        if self.network_enabled and self.data_mode is not DataMode.LIVE_PUBLIC:
            raise ValueError("only live_public may use public network data")
        return self


class ServiceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    database_path: Path
    universe_refresh_seconds: int = Field(ge=60)
    analysis_cycle_seconds: int = Field(ge=15)
    heartbeat_seconds: int = Field(ge=5)
    backup_interval_seconds: int = Field(ge=3600)
    backup_retention_days: int = Field(ge=1, le=365)
    log_path: Path
    backup_directory: Path
    model_directory: Path = Path("data/models")
    outcome_label_seconds: int = Field(default=300, ge=60)
    model_training_seconds: int = Field(default=86400, ge=3600)
    detailed_stream_limit: int = Field(ge=1, le=50)
    analysis_batch_size: int = Field(ge=1, le=10)
    watchlist: tuple[str, ...]
    horizons: tuple[Literal["5m", "15m", "1h", "4h", "1d"], ...]
    paper_simulation_enabled: bool = False
    automatic_paper_simulation_enabled: bool = False
    bind_host: Literal["127.0.0.1"] = "127.0.0.1"
    control_port: int = Field(ge=1024, le=65535)

    @model_validator(mode="after")
    def _safe_service(self) -> "ServiceSettings":
        if self.automatic_paper_simulation_enabled and not self.paper_simulation_enabled:
            raise ValueError("automatic paper mode requires paper simulation to be enabled")
        if not self.watchlist or not self.horizons:
            raise ValueError("service requires watchlist and horizons")
        return self

    def resolved_database_path(self) -> Path:
        return self.database_path if self.database_path.is_absolute() else PROJECT_ROOT / self.database_path

    def resolved_log_path(self) -> Path:
        return self.log_path if self.log_path.is_absolute() else PROJECT_ROOT / self.log_path

    def resolved_backup_directory(self) -> Path:
        return (
            self.backup_directory
            if self.backup_directory.is_absolute()
            else PROJECT_ROOT / self.backup_directory
        )

    def resolved_model_directory(self) -> Path:
        return self.model_directory if self.model_directory.is_absolute() else PROJECT_ROOT / self.model_directory


class ResearchSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    profile_name: Literal["fixture", "preview", "live_public", "replay"]
    profile: RuntimeProfile
    service: ServiceSettings


def load_research_settings(
    profile_name: str | None = None,
    *,
    path: str | Path = PROFILES_PATH,
) -> ResearchSettings:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    selected = cast(Literal["fixture", "preview", "live_public", "replay"], profile_name or raw.get("default_profile"))
    profiles = raw.get("profiles", {})
    if selected not in profiles:
        raise ValueError("unknown research profile")
    return ResearchSettings(
        profile_name=selected,
        profile=RuntimeProfile.model_validate(profiles[selected]),
        service=ServiceSettings.model_validate(raw.get("service", {})),
    )
