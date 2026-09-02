# Sources Architecture Plan

## 1. Component Boundaries & Unified Schema
* All scrapers inherit from `src/scrapers/base.py:BaseScraper`.
* HTTP-based scrapers generally share the `httpx.AsyncClient` created by `HorizonOrchestrator.fetch_all_sources()`; Playwright, optional SDK, and sidecar paths own their specialized lifecycles.
* Each scraper returns `list[ContentItem]`, where:
  * `id`: `{source}:{subtype}:{native_id}` format.
  * `source_type`: enum `SourceType`.
  * `url`: canonical direct link or deep post link.
  * `published_at`: normalized UTC timestamp.
  * `profile`: optional explicit/automatic profile route.
  * `metadata`: category tags and source-specific context.

## 2. Extraction & Ingestion Pipelines

### 2.1 YouTube Video Pipeline (`src/scrapers/video.py`)
* Channel RSS feeds provide initial video discovery without authentication.
* Content extraction ladder evaluates:
  1. Subtitles / VTT transcripts via `yt-dlp` (imported lazily inside methods to keep offline tests clean).
  2. Local ASR using `mlx-whisper` on Apple Silicon, releasing Metal buffer pool via `_release_asr()` in `finally`.
  3. Vision fallback summarizing storyboard grid frames via configured vision model.
* Sidecar mode (`src/services/video_cli.py`) decouples collection from the main pipeline and writes to configured `inbox_file` (`data/video-inbox.json` by default).

### 2.2 4PDA Forum Pipeline (`src/scrapers/fourpda.py`)
* Direct HTTP retrieval of target topic threads with `windows-1251` decoding.
* Date parsing converts relative Russian time phrases to MSK (UTC+3) before UTC normalization.
* Content cleaning strips `quote_body` blocks, edit notices, user badges, and rule headers; filters out posts under 15 characters.
* Known implementation gap: `FourPDAScraper` currently puts `cfg.profile` only in metadata instead of the top-level `ContentItem.profile`; the intended unified route contract above remains unchanged.

### 2.3 Community & News Feed Modules
* **Telegram** (`src/scrapers/telegram.py`): Parses public web previews through the `telegram.me`, `telegram.dog`, and `t.me` fallback hosts with rate-limit retries.
* **Reddit** (`src/scrapers/reddit.py`): Subreddit/post extraction via `old.reddit.com` and JSON endpoints.
* **RSS/Atom** (`src/scrapers/rss.py`): `feedparser` ingestion with optional Trafilatura full-text extraction.
* **Hacker News** (`src/scrapers/hackernews.py`): Firebase REST API stories and top comments.
* **GitHub** (`src/scrapers/github.py`): REST API releases and repository events.
* **GDELT & Google News** (`src/scrapers/gdelt.py`, `src/scrapers/google_news.py`): Multi-query news search.
* **OpenBB & OSS Insight** (`src/scrapers/openbb.py`, `src/scrapers/ossinsight.py`): Financial and open-source metric trends.
* **Twitter/X** (`src/scrapers/twitter.py`, `src/scrapers/twitter_playwright.py`): Apify `scweet` actor or Playwright/browser-cookie modes with graceful anti-bot degradation.

## 3. Ingestion Error Handling & Resilience
* `orchestrator._fetch_with_progress()` catches per-source exceptions so one scraper failure never halts the pipeline.
* YouTube metadata filters fail open: a missing duration or live-status field does not drop an item.
* Scraper execution status and item yield counts are recorded in `FetchReport`.
* Known gaps remain explicit:
  * configured RSS feed retrieval bypasses `safe_request()`, and its string-date fallback can be naive;
  * Google News relies on its query time operator instead of a local `since` filter and can also retain a naive string date;
  * Telegram and Reddit parse `Retry-After` only as an integer;
  * 4PDA profile propagation is described in §2.2.
