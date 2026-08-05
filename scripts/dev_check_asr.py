"""Mac-side ASR smoke test: transcribe a no-subtitles video via mlx-whisper."""
import asyncio
import json
import os

for line in open(".env", encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

import httpx

with open("data/config.json", encoding="utf-8") as f:
    raw = json.load(f)
ai = raw["ai"]
key = os.environ.get(ai["api_key_env"], "")
try:
    r = httpx.post(
        ai["base_url"].rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": ai["model"], "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
        timeout=30,
    )
    print(f"GATEWAY: {r.status_code}")
except Exception as e:
    print(f"GATEWAY UNREACHABLE: {e}")

from src.models import VideoConfig
from src.scrapers.video import VideoScraper

URL = "https://www.youtube.com/watch?v=ZgHIvU8XN80"

with open("data/config.json", encoding="utf-8") as f:
    vcfg = VideoConfig(**json.load(f)["sources"]["video"])

scraper = VideoScraper(vcfg, None)
result = asyncio.run(scraper._asr_local(URL))
if result:
    print(f"ASR OK, chars={len(result)}")
    print("HEAD:", result[:400].replace("\n", " | "))
else:
    print("ASR FAILED: no transcript")
