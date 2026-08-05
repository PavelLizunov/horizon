"""Standalone smoke-test for the Video scraper (dev utility, not part of pipeline).

This is the manual health check: it runs a real fetch over every enabled channel
and prints the extraction breakdown, so you can see which rung of the ladder is
actually carrying the load before the nightly run quietly stops finding text.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx

from src.models import VideoConfig
from src.scrapers.video import VideoScraper

# Preflight problems and the degradation warning are logged, not printed.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


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
                f"  url={it.url} source={it.metadata.get('content_source')} "
                f"duration={it.metadata.get('duration')} "
                f"content_len={len(it.content)}\n  head: {head}"
            )
        stats = scraper.last_run_stats
        print(f"TOTAL: {len(items)} items")
        print(f"BREAKDOWN: {stats.summary()}")
        print(f"TRANSCRIPT RATE: {stats.transcript_rate:.0%} (floor {cfg.min_transcript_rate:.0%})")


if __name__ == "__main__":
    asyncio.run(main())
