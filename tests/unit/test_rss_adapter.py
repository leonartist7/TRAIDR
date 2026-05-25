from intelligence.rss_adapter import RSSNewsAdapter


RSS = """<?xml version="1.0"?>
<rss><channel>
  <item><title>Token listing and product launch</title><link>https://example.test/a</link></item>
  <item><title>Exploit risk warning</title><link>https://example.test/b</link></item>
</channel></rss>
"""


def test_rss_adapter_parses_mocked_response_without_network() -> None:
    result = RSSNewsAdapter(lambda _url: RSS).fetch("https://example.test/rss")

    assert result.status == "OK"
    assert len(result.items) == 2
    assert result.can_execute_trades is False


def test_rss_adapter_network_failure_returns_insufficient_data() -> None:
    result = RSSNewsAdapter(lambda _url: (_ for _ in ()).throw(RuntimeError("offline"))).fetch("x")

    assert result.status == "INSUFFICIENT_DATA"
    assert "RSS_FETCH_FAILED" in result.reason_codes
