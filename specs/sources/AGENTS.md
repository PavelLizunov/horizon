# Sources SDD Guide (`specs/sources/AGENTS.md`)

This directory governs external source ingestion scrapers, content extraction ladders, resilient network anti-bot bypasses, and unified `ContentItem` schema normalization.

## 1. Document Trio Authority & Status

- **`spec.md`**: Defines this fork's YouTube and 4PDA source additions, their extraction ladders, cleaning rules, and shared ingestion constraints; it is not a complete registry of every implemented source.
- **`plan.md`**: Architecture for `BaseScraper` inheritance, shared `httpx.AsyncClient`, unified `ContentItem` schema, and `FetchReport` error isolation.
- **`tasks.md`**: Scraper implementation checklist. Changes must stay in sync with `src/scrapers/`, `src/models.py`, and `data/config.example.json`.
- **Hierarchy & Traceability**: `spec.md` > `plan.md` > `tasks.md`. Scraper extraction contracts map directly to scraper implementations under `src/scrapers/` and offline tests in `tests/`.

## 2. Local Non-Negotiable Invariants

1. **Graceful Degradation**: External scrapers must degrade gracefully on network failures, timeouts, rate limits, or IP blocks. Scrapers reduce item volume or detail, but must never raise unhandled exceptions or crash the pipeline.
2. **Offline Test Isolation**: All scrapers must pass offline unit tests (`pytest`) with mocked network responses. Heavy third-party network libraries (e.g. `yt-dlp`) are imported lazily inside methods to keep test suites offline.
3. **YouTube Invariants**:
   - Ingestion sequence: Channel RSS discovery, then content fallback Subtitles/VTT → local ASR (`mlx-whisper`) → vision.
   - ASR Metal buffer pool must be released in `fetch()`'s `finally` block (`_release_asr()`).
   - Metadata filters fail open (missing duration or status does not skip items).
4. **4PDA Invariants**:
   - Parse relative Russian dates in MSK timezone (UTC+3) before converting to UTC.
   - Strip quote blocks (`quote_body`), edit notes, user badges, and pinned rules prior to scoring.
   - Skip short posts (<15 chars) to preserve signal.
5. **Secret Protection**: Session cookie files (`youtube-cookies*.txt`) are top-secret credentials (`chmod 600`) and gitignored. Configuration stores environment variable names only (`api_key_env`).
