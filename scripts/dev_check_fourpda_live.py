import asyncio
from datetime import datetime, timezone, timedelta
import httpx

from src.models import FourPDAConfig, FourPDATopicConfig
from src.scrapers.fourpda import FourPDAScraper

async def main():
    async with httpx.AsyncClient() as client:
        cfg = FourPDAConfig(
            enabled=True,
            topics=[
                FourPDATopicConfig(
                    topic_id=1110469,
                    name="Суверенный Интернет – обсуждение",
                    category="ru-field-report",
                    profile="censorship-watch",
                    fetch_limit=15,
                )
            ]
        )
        scraper = FourPDAScraper(cfg, client)
        since = datetime.now(timezone.utc) - timedelta(hours=48)
        items = await scraper.fetch(since)
        print(f"Fetched {len(items)} items from 4PDA:")
        for it in items[-5:]:
            print(f"\n[{it.published_at}] {it.title}")
            print(f"URL: {it.url}")
            print(f"Author: {it.author}")
            print(f"Content: {it.content[:200]}...")

if __name__ == "__main__":
    asyncio.run(main())
