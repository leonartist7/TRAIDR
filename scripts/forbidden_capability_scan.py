"""Fail CI when forbidden real-money capabilities enter production source."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (
    "agents", "alerts", "ask", "cli", "config", "dashboard", "data_pipeline",
    "execution", "intelligence", "lifecycle", "memory", "notifications", "onchain",
    "operator", "portfolio", "radar", "reports", "risk", "scheduler", "scoring",
    "sentiment", "storage", "technicals", "thesis", "token_detail", "utils", "watchlist",
)
FORBIDDEN = (
    "create_private_order",
    "withdrawal_endpoint",
    "wallet_signing",
    "seed_phrase",
    "private_key_sign",
    "transfer_funds",
)
GUARD_IMPLEMENTATIONS = {Path("utils/toon.py")}


def main() -> int:
    findings: list[str] = []
    for root_name in SOURCE_ROOTS:
        root = ROOT / root_name
        for path in root.rglob("*.py"):
            if path.relative_to(ROOT) in GUARD_IMPLEMENTATIONS:
                continue
            lowered = path.read_text(encoding="utf-8").lower()
            for token in FORBIDDEN:
                if token in lowered:
                    findings.append(f"{path.relative_to(ROOT)}: {token}")
    if findings:
        print("Forbidden capabilities detected:\n" + "\n".join(findings))
        return 1
    print("Forbidden capability scan passed; public research and paper simulation only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
