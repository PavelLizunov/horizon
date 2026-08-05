"""Standalone: score one video item with the pipeline's ContentAnalyzer."""
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

for line in open(".env", encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from src.models import Config, ContentItem, SourceType
from src.ai.client import create_ai_client
from src.ai.analyzer import ContentAnalyzer
from src.processing import ProfileRegistry
from src.scrapers.video import VideoScraper, parse_vtt, format_transcript

URL = "https://www.youtube.com/watch?v=jxGJT1weu4w"

cfg = Config(**__import__("json").load(open("data/config.json", encoding="utf-8")))
profiles = ProfileRegistry.load(Path(cfg.processing.profiles_dir), cfg.processing.default_profile)


async def main():
    async with httpx.AsyncClient(timeout=120) as client:
        scraper = VideoScraper(cfg.sources.video, client, cfg.ai)
        vtt, info = scraper._download_subtitles(
            URL, cfg.sources.video.subtitle_langs, None, cfg.sources.video.cookies_file
        )
        transcript = format_transcript(parse_vtt(Path(vtt))) if vtt else ""
        item = ContentItem(
            id="video:youtube:jxGJT1weu4w",
            source_type=SourceType.VIDEO,
            title=info.get("title") or "untitled",
            url=URL,
            content="Transcript:\n" + transcript,
            author="Fireship",
            published_at=datetime.now(timezone.utc),
            profile="video",
            metadata={"channel": "Fireship", "has_transcript": bool(transcript)},
        )
        ai_client = create_ai_client(cfg.ai)
        analyzer = ContentAnalyzer(ai_client, profiles)
        await analyzer.analyze_batch([item])
        a = item.processing.analysis
        c = item.processing.classification
        print(f"SCORE: {a.score}")
        print(f"REASON: {a.reason}")
        print(f"SUMMARY: {a.summary[:200] if a.summary else None}")
        print(f"CLASSIFICATION: profile={c.profile} method={c.method} reason={c.reason}")


asyncio.run(main())
