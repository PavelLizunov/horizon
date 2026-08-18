"""Tests for 4PDA forum topic scraper."""

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest

from src.models import FourPDAConfig, FourPDATopicConfig, SourceType
from src.scrapers.fourpda import FourPDAScraper, parse_4pda_date, MSK_TZ


SAMPLE_4PDA_HTML = """
<!DOCTYPE html>
<html>
<head><title>Суверенный Интернет – обсуждение - 4PDA</title></head>
<body>
<div class="topic_title">Суверенный Интернет – обсуждение</div>

<!-- Pinned rules post: should be skipped -->
<div data-post="100000000">
  <div class="post_header"><span class="post_date">10.01.25, 10:00 | #1</span></div>
  <div class="post_nick"><a>Admin</a></div>
  <div class="post_body">Правила темы. Обход блокировок. """ + ("Правила " * 300) + """</div>
</div>

<!-- Valid post 1 -->
<div data-post="144704711">
  <div class="post_header">
    <span class="post_date">Вчера, 22:02 | <a href="https://4pda.to/forum/index.php?showtopic=1110469&view=findpost&p=144704711">#8820</a></span>
    <div class="post_nick"><a>doomlord00721<i class="icon">ᵥ</i></a></div>
  </div>
  <div class="post_body" id="post-main-144704711">
    <div class="quote_header">Цитата</div><div class="quote_body">Старый пост</div>
    Тоже вчера накатил обход бс через я.cdn. Полет нормальный, провайдер Т2 пропускает.
  </div>
</div>

<!-- Valid post 2 -->
<div data-post="144705580">
  <div class="post_header">
    <span class="post_date">Сегодня, 00:26 | <a href="https://4pda.to/forum/index.php?showtopic=1110469&view=findpost&p=144705580">#8822</a></span>
    <div class="post_nick"><a>meet37<i class="icon">ᵥ</i></a></div>
  </div>
  <div class="post_body" id="post-main-144705580">
    Свой vps - самая надежная подписка по цене пачки сигарет.
  </div>
</div>

<!-- Short trivial post: should be skipped -->
<div data-post="144705599">
  <div class="post_header">
    <span class="post_date">Сегодня, 01:00</span>
    <div class="post_nick"><a>user2</a></div>
  </div>
  <div class="post_body">
    +1
  </div>
</div>
</body>
</html>
"""


def test_parse_4pda_date():
    ref_time = datetime(2026, 8, 18, 12, 0, 0, tzinfo=MSK_TZ)
    
    # "Сегодня, 10:30"
    dt_today = parse_4pda_date("Сегодня, 10:30", now=ref_time)
    assert dt_today is not None
    assert dt_today == datetime(2026, 8, 18, 7, 30, 0, tzinfo=timezone.utc)
    
    # "Вчера, 22:02"
    dt_yesterday = parse_4pda_date("Вчера, 22:02", now=ref_time)
    assert dt_yesterday is not None
    assert dt_yesterday == datetime(2026, 8, 17, 19, 2, 0, tzinfo=timezone.utc)
    
    # "17.08.26, 18:43"
    dt_exact = parse_4pda_date("17.08.26, 18:43 | #8820")
    assert dt_exact is not None
    assert dt_exact == datetime(2026, 8, 17, 15, 43, 0, tzinfo=timezone.utc)


def test_fourpda_scraper_fetch():
    async def handler(request: httpx.Request) -> httpx.Response:
        encoded = SAMPLE_4PDA_HTML.encode("windows-1251", errors="replace")
        return httpx.Response(200, content=encoded, request=request)

    async def fetch_items():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            config = FourPDAConfig(
                enabled=True,
                topics=[
                    FourPDATopicConfig(
                        topic_id=1110469,
                        name="Суверенный Интернет",
                        category="ru-field-report",
                        profile="censorship-watch",
                        fetch_limit=10,
                    )
                ],
            )
            scraper = FourPDAScraper(config, client)
            since = datetime(2026, 8, 17, 0, 0, tzinfo=timezone.utc)
            return await scraper.fetch(since)

    items = asyncio.run(fetch_items())

    assert len(items) == 2
        
    # Check post 1
    item1 = items[0]
    assert item1.source_type == SourceType.FOURPDA
    assert item1.author == "doomlord00721"
    assert item1.id == "fourpda:topic:1110469:144704711"
    assert "я.cdn" in item1.content
    assert "Старый пост" not in item1.content  # quote stripped
    assert item1.metadata["category"] == "ru-field-report"
    assert item1.metadata["profile"] == "censorship-watch"
    assert "p=144704711" in str(item1.url)

    # Check post 2
    item2 = items[1]
    assert item2.author == "meet37"
    assert item2.id == "fourpda:topic:1110469:144705580"
    assert "Свой vps" in item2.content
