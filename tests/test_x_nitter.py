import feed_utils
import sources_international
import breaking


RSS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Test</title><item>
<title>Real Madrid confirm a signing</title><link>https://example.test/post</link>
</item></channel></rss>"""


class FakeResponse:
    def __init__(self, content=RSS_XML, error=None):
        self.content = content
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error


def test_nitter_sources_keep_mirror_fallbacks_and_cache(monkeypatch):
    monkeypatch.setattr(sources_international, "X_RSS_BASE_URL", "")
    monkeypatch.setattr(
        sources_international,
        "X_NITTER_INSTANCES",
        ("https://nitter-one.example", "https://nitter-two.example"),
    )
    monkeypatch.setattr(sources_international, "X_RSS_HANDLES", ("realmadrid",))
    monkeypatch.setattr(sources_international, "X_RSS_CACHE_SECONDS", 300)
    monkeypatch.setattr(sources_international, "X_RSS_BREAKING_ENTRY_SCAN_LIMIT", 6)

    source = sources_international.build_x_sources()[0]

    assert source["url"] == "https://nitter-one.example/realmadrid/rss"
    assert source["fallback_urls"] == ["https://nitter-two.example/realmadrid/rss"]
    assert source["kind"] == "x_official"
    assert source["cache_seconds"] == 300
    assert source["rss_require_entries"] is True
    assert source["rss_fetcher"] == "curl"
    assert source["breaking_entry_scan_limit"] == 6


def test_feed_parser_uses_second_mirror_after_first_fails(monkeypatch):
    calls = []
    feed_utils.clear_feed_cache()

    def fake_get(url, **_kwargs):
        calls.append(url)
        if url.startswith("https://first.example"):
            raise feed_utils.requests.ConnectionError("down")
        return FakeResponse()

    monkeypatch.setattr(feed_utils.requests, "get", fake_get)
    source = {
        "url": "https://first.example/realmadrid/rss",
        "fallback_urls": ["https://second.example/realmadrid/rss"],
        "rss_require_entries": True,
    }

    feed = feed_utils.parse_feed_url(source)

    assert len(feed.entries) == 1
    assert calls == [
        "https://first.example/realmadrid/rss",
        "https://second.example/realmadrid/rss",
    ]


def test_nitter_reposts_are_identified_before_editorial_selection():
    assert feed_utils.is_repost_entry({"title": "RT by @JLSanchez78: unrelated update"}) is True
    assert feed_utils.is_repost_entry({"title": "Real Madrid announce the squad"}) is False


def test_curl_fetcher_returns_feed_bytes(monkeypatch):
    class Result:
        returncode = 0
        stdout = RSS_XML
        stderr = b""

    monkeypatch.setattr(feed_utils.subprocess, "run", lambda *_args, **_kwargs: Result())

    content = feed_utils._fetch_feed_content(
        "https://nitter.example/realmadrid/rss",
        {"rss_fetcher": "curl"},
    )

    assert content == RSS_XML


def test_x_source_bootstrap_prevents_backfilled_breakings(monkeypatch, tmp_path):
    monkeypatch.setattr(breaking, "X_RSS_BOOTSTRAP_FILE", tmp_path / "x-bootstrap.json")
    source = {"label": "X - @realmadrid", "kind": "x_official"}
    entries = [{"link": "https://nitter.example/realmadrid/status/1"}]

    assert breaking.bootstrap_x_source(source, entries) is None
    assert breaking.bootstrap_x_source(source, entries) == {entries[0]["link"]}
