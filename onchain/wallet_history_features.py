"""Fixture wallet-history feature extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WalletHistoryFeatures:
    wallet: str
    early_entry_count: int | None
    win_loss_ratio: float | None
    rug_avoidance_rate: float | None
    developer_link_risk: bool | None
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "wallet": self.wallet,
            "early_entry_count": self.early_entry_count,
            "win_loss_ratio": self.win_loss_ratio,
            "rug_avoidance_rate": self.rug_avoidance_rate,
            "developer_link_risk": self.developer_link_risk,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": False,
        }


def extract_wallet_history_features(history: dict[str, Any] | None) -> WalletHistoryFeatures:
    if not history:
        return WalletHistoryFeatures("unknown", None, None, None, None, ("WALLET_HISTORY_UNKNOWN",))
    wallet = str(history.get("wallet") or "unknown")
    trades = history.get("trades") if isinstance(history.get("trades"), list) else []
    if not trades:
        return WalletHistoryFeatures(wallet, None, None, None, _bool_or_none(history.get("developer_link_risk")), ("WALLET_TRADES_UNKNOWN",))
    early = sum(1 for trade in trades if bool(trade.get("early_entry")))
    wins = sum(1 for trade in trades if trade.get("outcome") == "win")
    losses = sum(1 for trade in trades if trade.get("outcome") == "loss")
    rugs_seen = sum(1 for trade in trades if bool(trade.get("rugged")))
    rugs_avoided = sum(1 for trade in trades if bool(trade.get("avoided_rug")))
    ratio = wins / losses if losses else float(wins) if wins else None
    rug_rate = rugs_avoided / (rugs_seen + rugs_avoided) if rugs_seen + rugs_avoided else None
    return WalletHistoryFeatures(
        wallet,
        early,
        ratio,
        rug_rate,
        _bool_or_none(history.get("developer_link_risk")),
        ("WALLET_HISTORY_FEATURES_EXTRACTED",),
    )


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None
