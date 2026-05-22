import pytest

from utils.toon import UnsafePayloadError, serialize_toon


def test_toon_serializes_primitive_and_tabular_arrays() -> None:
    payload = {
        "pair": "SOL/USDC",
        "tags": ["simulation", "watch"],
        "signals": [
            {"name": "liquidity", "status": "known"},
            {"name": "freshness", "status": "fresh"},
        ],
    }

    assert serialize_toon(payload) == "\n".join(
        [
            'pair: SOL/USDC',
            "tags[2]: simulation,watch",
            "signals[2]{name,status}:",
            "  liquidity,known",
            "  freshness,fresh",
        ]
    )


def test_toon_rejects_secret_like_keys() -> None:
    with pytest.raises(UnsafePayloadError):
        serialize_toon({"safe": "summary", "private_key": "do-not-serialize"})

