"""One-off check: transcript, else vision fallback, for a specific video."""
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

from src.models import AIConfig, VideoConfig
from src.scrapers.video import VideoScraper, parse_vtt, format_transcript

URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=ZgHIvU8XN80"

for line in open(".env", encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

with open("data/config.json", encoding="utf-8") as f:
    raw = json.load(f)
vcfg = VideoConfig(**raw["sources"]["video"])
ai_cfg = AIConfig(**raw["ai"])


async def main():
    async with httpx.AsyncClient(timeout=120) as client:
        scraper = VideoScraper(vcfg, client, ai_cfg)
        vtt, info = scraper._download_subtitles(
            URL, vcfg.subtitle_langs, vcfg.cookies_from_browser, vcfg.cookies_file
        )
        print("TITLE:", info.get("title"))
        if vtt:
            tr = format_transcript(parse_vtt(Path(vtt)))
            print(f"SUBTITLES OK chars={len(tr)}")
            print("HEAD:", tr[:300].replace("\n", " | "))
            return
        print("NO SUBTITLES -> trying vision fallback")
        frames = await asyncio.to_thread(scraper._fetch_storyboard, URL)
        print(f"STORYBOARD FRAMES: {len(frames)}")
        if not frames:
            print("RESULT: no storyboard either")
            return
        summary = await scraper._vision_summarize(frames[: vcfg.vision_max_frames])
        print("VISION SUMMARY:", summary)


asyncio.run(main())
