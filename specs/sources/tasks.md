# Sources Tasks & Implementation Checklist

- [x] Implement YouTube video source with subtitles / local ASR / vision fallback (`src/scrapers/video.py`).
- [x] Implement YouTube sidecar CLI (`src/services/video_cli.py`).
- [x] Add 4PDA Russian forum topic scraper with windows-1251 encoding and MSK date parsing (`src/scrapers/fourpda.py`).
- [x] Clean quotes, reply previews, and noise in 4PDA posts.
- [x] Implement community and news feed scrapers (Telegram, Reddit, RSS/Atom, Hacker News, GitHub, OpenBB, OSS Insight, GDELT, Google News, Twitter/X).
- [x] Add offline source regression suites (`tests/test_video.py`, `tests/test_fourpda.py`, `tests/test_telegram.py`, `tests/test_reddit.py`, `tests/test_rss.py`, `tests/test_gdelt.py`, `tests/test_google_news.py`, `tests/test_openbb_scraper.py`, `tests/test_twitter.py`, `tests/test_category_wiring.py`).
- [x] Support multiple query definitions for GDELT and Google News.
- [x] Document 4PDA and YouTube configuration in tracked examples. Live `data/config.json` remains untracked operator state and is not asserted by this checklist.

## Known hardening backlog

- [ ] Route configured RSS feed retrieval through the shared public-address guard and normalize all fallback dates to aware UTC without aborting the rest of a feed.
- [ ] Apply a local `published_at >= since` filter in Google News and normalize direct string-date fallbacks to aware UTC.
- [ ] Propagate `FourPDATopicConfig.profile` to top-level `ContentItem.profile` while retaining any compatibility metadata.
- [ ] Parse both delta-seconds and HTTP-date forms of `Retry-After` in Reddit and Telegram.
