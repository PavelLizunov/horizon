# AGENTS.md — Scraper Layer Guide (`src/scrapers/`)

This directory contains source scrapers for Horizon. Inherits rules from root [`AGENTS.md`](../../AGENTS.md) and [`src/AGENTS.md`](../AGENTS.md).

## 1. Architecture & Interface

All scrapers inherit from `BaseScraper` (`src/scrapers/base.py`) and share an async HTTP client (`httpx.AsyncClient`).

```python
class BaseScraper(ABC):
    def __init__(self, config: dict, http_client: httpx.AsyncClient): ...
    @abstractmethod
    async def fetch(self, since: datetime) -> List[ContentItem]: ...
```

*Note*: `VideoScraper` additionally accepts `ai_config` (`AIConfig`), and `RSSScraper` accepts `ExtractorRegistry`.
Scrapers execute concurrently via `asyncio.gather` inside `HorizonOrchestrator.fetch_all_sources()` (`src/orchestrator.py`).

## 2. Core Invariants & Contract Rules

### 2.1 Source Addition Parity (7-Step Contract)
Adding or updating a source requires synchronized changes across 7 locations:
1. `src/models.py`: Add enum value to `SourceType`.
2. `src/models.py`: Add Pydantic config model & register `SourceDefinition` in `SOURCE_REGISTRY`.
3. `src/models.py`: Add optional config attribute to `SourcesConfig`.
4. `src/scrapers/`: Create scraper module `src/scrapers/<source>.py` extending `BaseScraper`.
5. `src/orchestrator.py`: Instantiate and register fetch task in `HorizonOrchestrator.fetch_all_sources()`.
6. `data/config.example.json`: Add documented default configuration section.
7. `tests/`: Add offline unit/integration test suite under `tests/`.

### 2.2 Per-Source Graceful Degradation
- A healthy source with no matching items returns `[]`; disabled/config-empty sources and missing optional dependencies also skip cleanly.
- Multi-endpoint scrapers retain results (including a healthy empty result) when only some endpoints fail, but raise when every attempted endpoint fails operationally.
- `_fetch_with_progress` catches scraper-wide failures, logs them, and returns `SourceFetchOutcome(status="failure", error=...)`, so one failed scraper never crashes the orchestrator run.
- Optional metadata parsing failures (e.g. missing video live status, author, or duration) fail open and retain valid content.
- Video is the documented exception: it never raises and instead exposes degradation through `VideoRunStats`.

### 2.3 UTC & Time-Window Semantics
- `fetch(since: datetime)` accepts a timezone-aware UTC datetime.
- All `ContentItem.published_at` values **must be timezone-aware UTC** (`datetime.now(timezone.utc)` or `.astimezone(timezone.utc)`).
- Timezone conversions must occur before constructing `ContentItem`:
  - 4PDA dates (Moscow time `UTC+3`) parsed in MSK and converted via `.astimezone(timezone.utc)`.
  - Unix timestamps (HN, Reddit) converted via `datetime.fromtimestamp(ts, tz=timezone.utc)`.
- Items published strictly before `since` (`published_at < since`) must be filtered out.

### 2.4 Stable ContentItem Schema
`ContentItem` (`src/models.py`) uses `ConfigDict(extra="forbid")`.
- **Standard fields**: `id`, `source_type`, `title`, `url` (`HttpUrl`), `content`, `author`, `published_at`, `fetched_at`, `metadata`, requested `profile`, and optional downstream `processing`.
- **ID Generation**: Call `self._generate_id(source_type, subtype, native_id)` to produce `{source_type}:{subtype}:{native_id}`.
- **Custom Metadata**: Source-specific attributes (e.g. upvotes, comment counts, star counts, flair, watchlist symbols) **must** be stored inside `item.metadata` dict, never on top-level `ContentItem` fields.

### 2.5 Config, API & Dependency Compatibility
- Secrets (API keys, tokens) are referenced by environment variable names (e.g., `api_key_env`, `apify_token_env`), loaded via `.env`. Never store raw key strings in config files or models.
- Heavy/platform dependencies must stay behind lazy import boundaries where implemented. `openbb`, `mlx-whisper`, and Playwright are optional extras; `yt-dlp` is a standard dependency but is still imported lazily so partial installations degrade cleanly.

### 2.6 Known Audit Gaps (Do Not Copy)
- Google News uses its query time operator but does not locally enforce `published_at >= since`, and its string-date fallback is not normalized to UTC.
- Reddit and Telegram assume `Retry-After` is an integer even though the header may legally be an HTTP date.

## 3. Special Scraper Invariants

### 3.1 YouTube Video Scraper (`src/scrapers/video.py`)
- **RSS Discovery**: Discovers videos via `https://www.youtube.com/feeds/videos.xml?channel_id=...` without API keys.
- **Fallback Ladder**: Subtitles (`yt-dlp` VTT cues) → Local ASR (`mlx-whisper` on Apple Silicon) → Vision fallback (storyboard frame grids sent to vision LLM). First successful text wins.
- **Lazy Imports & Memory**: `yt-dlp` imported lazily inside methods. Metal buffer pool purged via `_release_asr()` in `fetch()`'s `finally` block.
- **Degradation Visibility**: Emits `VideoRunStats` summary and logs `WARNING` when transcript rate is under `min_transcript_rate`. Bot-gated (cookie prompt) errors tracked explicitly.

### 3.2 4PDA Forum Scraper (`src/scrapers/fourpda.py`)
- **Encoding**: HTML pages fetched explicitly with `windows-1251` character encoding.
- **Date Conversion**: Relative/absolute Russian dates (*«Сегодня»*, *«Вчера»*, *«DD.MM.YY»*) parsed in Moscow time (`UTC+3`) before converting to UTC.
- **Sanitization**: Strips quote blocks (`quote_body`), edit notes, user badges, and pinned FAQ rules to avoid scoring old quoted text.
- **Filtering**: Skips posts under 15 characters and FAQ headers.
- **Deep Links**: Links directly to individual post IDs (`&view=findpost&p={post_id}`).

## 4. Test Coverage & Network Mocking

All scraper tests run strictly offline. Network calls are mocked via `httpx.MockTransport`, `unittest.mock.AsyncMock`, or local HTML/JSON fixtures.

| Scraper Module | Scraper Class | Primary Test File | Coverage Focus |
|---|---|---|---|
| `fourpda.py` | `FourPDAScraper` | `tests/test_fourpda.py` | Encoding, MSK date parsing, quote stripping, deep links |
| `video.py` | `VideoScraper` | `tests/test_video.py` | RSS parsing, VTT cleanup, fallback ladder, offline stats |
| `rss.py` | `RSSScraper` | `tests/test_rss.py` | URL safety, Atom/RSS parsing, UTC date fallbacks, extractor integration, failure aggregation |
| `reddit.py` | `RedditScraper` | `tests/test_reddit.py` | Subreddit/user fetching, old.reddit parsing, 429 retries |
| `telegram.py` | `TelegramScraper` | `tests/test_telegram.py` | Web preview HTML parsing, channel message filtering |
| `twitter.py` / `twitter_playwright.py` | `TwitterScraper`, `TwitterPlaywrightScraper` | `tests/test_twitter.py` | Apify polling, reply thread expansion, Playwright fallback |
| `openbb.py` | `OpenBBScraper` | `tests/test_openbb_scraper.py` | Thread execution, lazy import, watchlist deduplication |
| `gdelt.py` | `GDELTScraper` | `tests/test_gdelt.py` | GDELT 2.0 DOC API response parsing, query formatting |
| `google_news.py` | `GoogleNewsScraper` | `tests/test_google_news.py` | RSS parsing, query/time operators, CEID defaults, result limits |
| `github.py` | `GitHubScraper` | `tests/test_category_wiring.py`, `tests/test_fetch_reporting.py` | User events, repo releases, token auth, error recovery |
| `hackernews.py` | `HackerNewsScraper` | `tests/test_category_wiring.py`, `tests/test_fetch_reporting.py` | Firebase API, top stories, comment extraction, min_score |
| `ossinsight.py` | `OSSInsightScraper` | `tests/test_category_wiring.py` | API parsing, trending repo metric extraction |
