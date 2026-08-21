# Sources Specification

## 1. Objective
Acquire content items from diverse heterogeneous external sources (social feeds, video channels, discussion boards, code repositories, RSS feeds, search APIs) in a unified `ContentItem` schema, with resilient anti-bot bypass, fallback ladders, and graceful degradation.

---

## 2. Supported Sources

### 2.1 YouTube Video Source (`sources.video`)
* **Discovery**: Channel RSS feeds (`https://www.youtube.com/feeds/videos.xml?channel_id=...`).
* **Extraction Ladder**:
  1. Subtitles / VTT transcripts (de-duplicated).
  2. Local ASR (`mlx-whisper` on Apple Silicon).
  3. Vision fallback (storyboard grid frames summarized by vision model).
* **Modes**: `inline` (run inside pipeline) or `sidecar` (`horizon-video` writes `data/video-inbox.json`).

### 2.2 4PDA Forum Topics (`sources.fourpda`)
* **Target**: Discussion threads on ISP blocks, DPI filters, and VPN bypass (e.g. topic `1110469`).
* **Encoding**: `windows-1251`.
* **Date Parsing**: Relative Russian dates (*«Сегодня, 14:20»*, *«Вчера, 23:26»*, *«DD.MM.YY»*) in Moscow time (UTC+3) converted to UTC.
* **Cleaning**: Quote boxes (`quote_body`), edit notes, and user badge icons stripped. Short posts (<15 chars) and pinned rule headers skipped.

### 2.3 Community & News Feeds
* **Telegram** (`sources.telegram`): Public web channel previews (`https://t.me/s/...`), rate-limit retries.
* **Reddit** (`sources.reddit`): Subreddits and user submissions via `old.reddit.com` and JSON fallbacks.
* **RSS/Atom** (`sources.rss`): Feedparser with date fallbacks and optional Trafilatura full-text extraction.
* **Hacker News** (`sources.hackernews`): Top stories and top comments via Firebase API.
* **GitHub** (`sources.github`): Releases and user events via GitHub REST API.
* **GDELT & Google News** (`sources.gdelt`, `sources.google_news`): Keyless global and regional news search.
* **OpenBB & OSS Insight** (`sources.openbb`, `sources.ossinsight`): Financial and open-source metric trends.
