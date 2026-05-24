"""Terminal formatting for token detail cards."""

from __future__ import annotations

import json
from typing import Any

from cli.formatters import key_values, section
from token_detail.detail_models import TokenDetailReport


def format_token_detail(report: TokenDetailReport) -> str:
    identity = report.identity.to_dict() if report.identity else {}
    technical = report.technical_vector or {"status": report.technical_vector_status}
    return "\n\n".join(
        (
            section(
                "Token Detail",
                key_values(
                    {
                        "status": report.status,
                        "pair_id": identity.get("pair_id", "none"),
                        "chain": identity.get("chain", "none"),
                        "base_symbol": identity.get("base_symbol", "none"),
                        "quote_symbol": identity.get("quote_symbol", "none"),
                        "source": identity.get("source", "none"),
                        "price_usd": _render(report.price_usd),
                        "liquidity_usd": _render(report.liquidity_usd),
                        "volume_24h_usd": _render(report.volume_24h_usd),
                        "liquidity_score": report.liquidity_score,
                        "opportunity_score": report.opportunity_score,
                        "risk_score": report.risk_score,
                        "anti_rug_status": report.anti_rug.status,
                        "unknown_safety_fields": report.anti_rug.unknown_fields,
                        "radar_state": report.radar_state,
                        "reason_codes": report.reason_codes,
                        "can_execute_trades": report.can_execute_trades,
                    }
                ).splitlines(),
            ),
            section("Technical Vector", [json.dumps(technical, sort_keys=True, separators=(",", ":"))]),
            section("Why Interesting", [report.why_interesting]),
            section("Why Risky", [report.why_risky]),
        )
    )


def _render(value: Any) -> Any:
    return "none" if value is None else value
