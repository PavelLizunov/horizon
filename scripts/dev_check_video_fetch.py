"""Standalone smoke-test for the Video scraper (dev utility, not part of pipeline)."""
import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx

from src.models import VideoConfig
from src.scrapers.video import VideoScraper


async def main():
    with open("data/config.json", encoding="utf-8") as f:
        raw = json.load(f)
    cfg = VideoConfig(**raw["sources"]["video"])
    async with httpx.AsyncClient(timeout=60) as client:
        scraper = VideoScraper(cfg, client)
        since = datetime.now(timezone.utc) - timedelta(days=7)
        items = await scraper.fetch(since)
        for it in items:
            head = it.content[:120].replace("\n", " ")
            print(
                f"- [{it.author}] {it.title}\n"
                f"  url={it.url} transcript={it.metadata.get('has_transcript')} "
                f"content_len={len(it.content)}\n  head: {head}"
            )
        print(f"TOTAL: {len(items)} items")


if __name__ == "__main__":
    asyncio.run(main())
