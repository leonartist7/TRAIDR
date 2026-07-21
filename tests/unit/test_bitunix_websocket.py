import json
from datetime import UTC, datetime

from data_pipeline.bitunix_websocket import BitunixPublicStream
from intelligence.production_models import EventQuality, MarketChannel


NOW = datetime(2026, 7, 20, 12, tzinfo=UTC)


def test_public_stream_builds_only_allowlisted_public_subscriptions() -> None:
    stream = BitunixPublicStream(("BTCUSDT",), intervals=("1m",))
    request = stream.subscription_request()

    assert request["op"] == "subscribe"
    assert len(request["args"]) == 5
    assert all(item["symbol"] == "BTCUSDT" for item in request["args"])
    assert "login" not in json.dumps(request).lower()


def test_public_stream_parses_ticker_and_flags_out_of_order_frames() -> None:
    stream = BitunixPublicStream(("BTCUSDT",), intervals=("1m",))
    first = stream.parse_message(
        json.dumps(
            {
                "ch": "ticker",
                "symbol": "BTCUSDT",
                "ts": int(NOW.timestamp() * 1000),
                "data": {"s": "BTCUSDT", "la": "68000", "o": "67000", "h": "69000", "l": "66000", "b": "10", "q": "680000"},
            }
        ),
        received_at=NOW,
    )[0]
    second = stream.parse_message(
        json.dumps(
            {
                "ch": "ticker",
                "symbol": "BTCUSDT",
                "ts": int(NOW.timestamp() * 1000) - 1,
                "data": {"s": "BTCUSDT", "la": "67999"},
            }
        ),
        received_at=NOW,
    )[0]

    assert first.channel is MarketChannel.TICKER
    assert first.quality is EventQuality.SUFFICIENT
    assert first.can_execute_trades is False
    assert second.quality is EventQuality.CONTRADICTORY
    assert "BITUNIX_WS_OUT_OF_ORDER" in second.reason_codes
