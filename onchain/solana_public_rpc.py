"""Credential-free, read-only Solana mint and largest-account evidence."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from onchain.contracts import OnchainSafetyObservation


SOLANA_PUBLIC_RPC_URL = "https://api.mainnet-beta.solana.com"
RpcTransport = Callable[[str, list[Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class SolanaMintEvidence:
    mint_address: str
    supply: int
    decimals: int
    mint_authority_present: bool
    freeze_authority_present: bool
    largest_holder_fraction: float | None
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def safety_observation(self) -> OnchainSafetyObservation:
        unsafe_control = self.mint_authority_present or self.freeze_authority_present
        concentration = self.largest_holder_fraction is not None and self.largest_holder_fraction >= 0.80
        return OnchainSafetyObservation(
            mint_freeze_or_sell_restriction=self.freeze_authority_present,
            unsafe_holder_or_creator_control=unsafe_control or concentration,
            identity_ambiguous=False,
            evidence_complete=self.largest_holder_fraction is not None,
        )


class SolanaPublicRpcAdapter:
    def __init__(self, transport: RpcTransport | None = None) -> None:
        self.transport = transport or default_solana_rpc_transport

    def fetch_mint_evidence(self, mint_address: str) -> SolanaMintEvidence | None:
        if not mint_address or len(mint_address) < 32:
            return None
        try:
            account = self.transport("getAccountInfo", [mint_address, {"encoding": "base64"}])
            largest = self.transport("getTokenLargestAccounts", [mint_address])
            raw = _account_bytes(account)
            supply, decimals, mint_authority, freeze_authority = _parse_mint(raw)
            largest_fraction = _largest_holder_fraction(largest, supply)
        except (KeyError, TypeError, ValueError, RuntimeError):
            return None
        reasons = ["SOLANA_PUBLIC_RPC", "MINT_LAYOUT_VALIDATED"]
        if mint_authority:
            reasons.append("SOLANA_MINT_AUTHORITY_PRESENT")
        if freeze_authority:
            reasons.append("SOLANA_FREEZE_AUTHORITY_PRESENT")
        return SolanaMintEvidence(
            mint_address=mint_address,
            supply=supply,
            decimals=decimals,
            mint_authority_present=mint_authority,
            freeze_authority_present=freeze_authority,
            largest_holder_fraction=largest_fraction,
            reason_codes=tuple(reasons),
        )


def default_solana_rpc_transport(method: str, params: list[Any]) -> Mapping[str, Any]:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    request = Request(
        SOLANA_PUBLIC_RPC_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "TRAIDR-read-only-research/0.2"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            parsed = json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Solana public RPC failed") from exc
    if not isinstance(parsed, Mapping) or parsed.get("error"):
        raise RuntimeError("Solana public RPC returned an error")
    return parsed


def _account_bytes(payload: Mapping[str, Any]) -> bytes:
    value = payload["result"]["value"]
    encoded = value["data"][0]
    return base64.b64decode(encoded)


def _parse_mint(raw: bytes) -> tuple[int, int, bool, bool]:
    if len(raw) < 82:
        raise ValueError("Solana mint account is too short")
    mint_option = int.from_bytes(raw[0:4], "little")
    supply = int.from_bytes(raw[36:44], "little")
    decimals = raw[44]
    initialized = raw[45]
    freeze_option = int.from_bytes(raw[46:50], "little")
    if initialized != 1 or mint_option not in {0, 1} or freeze_option not in {0, 1}:
        raise ValueError("Solana mint layout is contradictory")
    return supply, decimals, mint_option == 1, freeze_option == 1


def _largest_holder_fraction(payload: Mapping[str, Any], supply: int) -> float | None:
    if supply <= 0:
        return None
    values = payload.get("result", {}).get("value", [])
    amounts = [int(item["amount"]) for item in values if isinstance(item, Mapping) and item.get("amount")]
    return max(amounts) / supply if amounts else None
