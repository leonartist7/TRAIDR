"""Smart-wallet profile assembly from fixture histories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from onchain.wallet_history_features import WalletHistoryFeatures, extract_wallet_history_features


@dataclass(frozen=True)
class WalletProfile:
    wallet: str
    features: WalletHistoryFeatures
    evidence_complete: bool
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "wallet": self.wallet,
            "features": self.features.to_dict(),
            "evidence_complete": self.evidence_complete,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": False,
        }


def build_wallet_profile(history: dict[str, Any] | None) -> WalletProfile:
    features = extract_wallet_history_features(history)
    complete = (
        features.early_entry_count is not None
        and features.win_loss_ratio is not None
        and features.rug_avoidance_rate is not None
        and features.developer_link_risk is not None
    )
    reasons = ["WALLET_PROFILE_COMPLETE"] if complete else ["WALLET_PROFILE_INCOMPLETE"]
    reasons.extend(features.reason_codes)
    return WalletProfile(features.wallet, features, complete, tuple(dict.fromkeys(reasons)))
