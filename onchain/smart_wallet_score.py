"""Score smart-wallet evidence separately from token safety."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from onchain.wallet_cluster_scorer import WalletClusterScore
from onchain.wallet_profiles import WalletProfile


@dataclass(frozen=True)
class SmartWalletScore:
    smart_wallet_score: Decimal | None
    wallet_cluster_risk_score: Decimal
    evidence_complete: bool
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "smart_wallet_score": str(self.smart_wallet_score) if self.smart_wallet_score is not None else None,
            "wallet_cluster_risk_score": str(self.wallet_cluster_risk_score),
            "evidence_complete": self.evidence_complete,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": False,
        }


def score_smart_wallet(profile: WalletProfile, cluster_score: WalletClusterScore | None = None) -> SmartWalletScore:
    reasons: list[str] = []
    cluster_risk = cluster_score.wallet_cluster_risk_score if cluster_score is not None else Decimal("0")
    if not profile.evidence_complete:
        return SmartWalletScore(None, cluster_risk, False, ("SMART_WALLET_EVIDENCE_INCOMPLETE",))
    features = profile.features
    score = Decimal("0")
    score += Decimal(min(features.early_entry_count or 0, 5) * 10)
    score += Decimal(str(min(features.win_loss_ratio or 0, 3))) * Decimal("10")
    score += Decimal(str(features.rug_avoidance_rate or 0)) * Decimal("25")
    reasons.append("SMART_WALLET_HISTORY_SCORED")
    if features.developer_link_risk:
        score -= Decimal("40")
        reasons.append("DEVELOPER_LINK_RISK")
    if cluster_score is not None:
        score -= cluster_risk / Decimal("2")
        reasons.extend(cluster_score.reason_codes)
    bounded = max(Decimal("0"), min(Decimal("100"), score))
    return SmartWalletScore(bounded, cluster_risk, True, tuple(dict.fromkeys(reasons)))
