from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.models import RSSSourceConfig
from src.scrapers.rss import RSSScraper
from src.url_security import UnsafeURLError

_FEED = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"><channel><title>Test</title>
  <item>
    <guid>entry-1</guid>
    <title>Item 1</title>
    <link>https://example.com/item-1</link>
    <pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>
    <description>Short summary from feed.</description>
  </item>
</channel></rss>
"""
_SINCE = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _mock_dns():
    def fake_getaddrinfo(host, port, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", port))]

    with patch("src.url_security.socket.getaddrinfo", side_effect=fake_getaddrinfo):
        yield


def _make_feed_client(feed_text: str) -> httpx.AsyncClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=feed_text, request=request)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_rss_ids_are_deterministic() -> None:
    client = _make_feed_client(_FEED)
    source = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", profile="rss-profile"
    )
    scraper = RSSScraper([source], client)

    first_item = asyncio.run(scraper.fetch(_SINCE))[0]
    first = first_item.id
    second = asyncio.run(scraper.fetch(_SINCE))[0].id

    assert first == second
    assert first == "rss:example.com_feed.xml:5e2d5d1e58e94d76"
    assert first_item.profile == "rss-profile"


def _make_registry(name: str, extractor):
    registry = MagicMock()
    registry.get.side_effect = lambda n: extractor if n == name else None
    return registry


def test_content_extractor_replaces_feed_content() -> None:
    client = _make_feed_client(_FEED)
    extractor = AsyncMock()
    extractor.extract.return_value = "Full article text from extractor."

    source = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", content_extractor="my-ext"
    )
    scraper = RSSScraper([source], client, extractors=_make_registry("my-ext", extractor))
    items = asyncio.run(scraper.fetch(_SINCE))

    assert len(items) == 1
    assert items[0].content == "Full article text from extractor."
    extractor.extract.assert_awaited_once_with("https://example.com/item-1", client)


def test_content_extractor_falls_back_on_none() -> None:
    client = _make_feed_client(_FEED)
    extractor = AsyncMock()
    extractor.extract.return_value = None  # extraction failed

    source = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", content_extractor="my-ext"
    )
    scraper = RSSScraper([source], client, extractors=_make_registry("my-ext", extractor))
    items = asyncio.run(scraper.fetch(_SINCE))

    assert len(items) == 1
    assert items[0].content == "Short summary from feed."


def test_unknown_extractor_name_ignored() -> None:
    client = _make_feed_client(_FEED)
    source = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", content_extractor="nonexistent"
    )
    scraper = RSSScraper([source], client, extractors=_make_registry("other", AsyncMock()))
    items = asyncio.run(scraper.fetch(_SINCE))

    assert len(items) == 1
    assert items[0].content == "Short summary from feed."


def test_rss_routes_through_safe_request_and_blocks_private_destinations() -> None:
    client = _make_feed_client(_FEED)
    source = RSSSourceConfig(
        name="PrivateFeed", url="http://127.0.0.1/feed.xml"
    )
    scraper = RSSScraper([source], client)
    with pytest.raises(RuntimeError, match="All RSS feeds failed") as exc_info:
        asyncio.run(scraper.fetch(_SINCE))
    assert isinstance(exc_info.value.__cause__, UnsafeURLError)


def test_rss_reports_failure_when_every_enabled_feed_fails() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )
    sources = [
        RSSSourceConfig(name="One", url="https://example.com/one.xml"),
        RSSSourceConfig(name="Two", url="https://example.com/two.xml"),
    ]

    with pytest.raises(RuntimeError, match="All RSS feeds failed") as exc_info:
        asyncio.run(RSSScraper(sources, client).fetch(_SINCE))

    assert isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)


def test_rss_partial_healthy_empty_succeeds_when_one_feed_fails() -> None:
    empty_feed = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel><title>Empty Feed</title>
    </channel></rss>
    """

    async def handler(request: httpx.Request) -> httpx.Response:
        if "fail" in str(request.url):
            return httpx.Response(500, text="Server Error", request=request)
        return httpx.Response(200, text=empty_feed, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sources = [
        RSSSourceConfig(name="FailingFeed", url="https://example.com/fail.xml"),
        RSSSourceConfig(name="EmptyHealthyFeed", url="https://example.com/empty.xml"),
    ]
    scraper = RSSScraper(sources, client)

    items = asyncio.run(scraper.fetch(_SINCE))
    assert items == []


@pytest.mark.parametrize(
    "value",
    [
        "24 Apr 2026 12:00:00 -0000",
        "Fri, 24 Apr 2026 15:00:00 +0300",
        "2026-04-24T15:00:00+03:00",
    ],
)
def test_rss_string_dates_are_normalized_to_utc(value) -> None:
    parsed = RSSScraper([], _make_feed_client(_FEED))._parse_date({"published": value})

    assert parsed == datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)


def test_rss_bad_entry_does_not_block_later_utc_entry() -> None:
    feed_text = """<rss version="2.0"><channel><title>Test</title>
      <item><guid>bad</guid><title>Bad URL</title><link>not-a-url</link>
        <published>24 Apr 2026 12:00:00 -0000</published></item>
      <item><guid>good</guid><title>Good</title><link>https://example.com/good</link>
        <published>24 Apr 2026 12:00:00 -0000</published></item>
    </channel></rss>"""
    source = RSSSourceConfig(name="Test", url="https://example.com/feed.xml")

    items = asyncio.run(RSSScraper([source], _make_feed_client(feed_text)).fetch(_SINCE))

    assert [item.title for item in items] == ["Good"]
    assert items[0].published_at == datetime(
        2026, 4, 24, 12, 0, tzinfo=timezone.utc
    )
