# Sources Tasks & Implementation Checklist

- [x] Implement YouTube video source with subtitles / local ASR / vision fallback (`src/scrapers/video.py`).
- [x] Implement YouTube sidecar daemon CLI (`src/services/video_cli.py`).
- [x] Add 4PDA Russian forum topic scraper with windows-1251 encoding and MSK date parsing (`src/scrapers/fourpda.py`).
- [x] Clean quotes, reply previews, and noise in 4PDA posts.
- [x] Add offline pytest unit tests for all scrapers (`tests/test_video.py`, `tests/test_fourpda.py`, `tests/test_telegram.py`, `tests/test_reddit.py`, etc.).
- [x] Support multiple query definitions for GDELT and Google News.
- [x] Integrate 4PDA and new YouTube channels into `data/config.example.json` and production `data/config.json`.
