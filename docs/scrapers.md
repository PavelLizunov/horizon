---
layout: default
title: Source Scrapers
---

# Source Scrapers

Horizon fetches content from multiple source types. All scrapers inherit from `BaseScraper`, share an async HTTP client, and implement a `fetch(since)` method that returns a list of `ContentItem` objects. Sources are fetched concurrently via `asyncio.gather`.

## Hacker News

**File**: `src/scrapers/hackernews.py`

Uses the [Firebase HN API](https://hacker-news.firebaseio.com/v0):

- `GET /topstories.json` — fetches top story IDs
- `GET /item/{id}.json` — fetches story/comment details

Stories and their comments are fetched concurrently. For each story, the top 5 comments are included (deleted/dead comments excluded, HTML stripped, truncated at 500 chars).

**Config** (`sources.hackernews`):

```json
{
  "enabled": true,
  "fetch_top_stories": 30,
  "min_score": 100,
  "category": "tech"
}
```

- `fetch_top_stories` — number of top story IDs to fetch
- `min_score` — minimum HN points to include a story
- `category` — optional tag for balanced digest grouping

**Extracted data**: title, URL (falls back to HN discussion URL), author, score, comment count, top comment text, and category.

## GitHub

**File**: `src/scrapers/github.py`

Uses the [GitHub REST API](https://api.github.com):

- `GET /users/{username}/events/public` — user activity events
- `GET /repos/{owner}/{repo}/releases` — repository releases

Two source types are supported:

- **`user_events`** — tracks push, create, release, public, and watch events for a user
- **`repo_releases`** — tracks new releases for a specific repository

**Config** (`sources.github`, list of entries):

```json
{
  "type": "user_events",
  "username": "torvalds",
  "enabled": true,
  "category": "oss"
}
```

```json
{
  "type": "repo_releases",
  "owner": "golang",
  "repo": "go",
  "enabled": true,
  "category": "oss"
}
```

- `category` — optional tag for balanced digest grouping; set per source entry

**Authentication**: Set `GITHUB_TOKEN` in your environment for higher rate limits (5000 req/hr vs 60 without).

## RSS

**File**: `src/scrapers/rss.py`

Fetches any Atom/RSS feed using the `feedparser` library. Tries multiple date fields (`published`, `updated`, `created`) with fallback parsing.

**Config** (`sources.rss`, list of entries):

```json
{
  "name": "Simon Willison",
  "url": "https://simonwillison.net/atom/everything/",
  "enabled": true,
  "category": "ai-tools",
  "content_extractor": "trafilatura"
}
```

- `category` — optional tag for grouping (e.g., `"programming"`, `"microblog"`)
- `content_extractor` — optional name of an extractor defined in `extractors` config; when set, the full article text replaces the feed-provided excerpt (see [Extractors](extractors.md))

**Extracted data**: title, URL, author, content (from `summary`/`description`/`content` fields, or full article text if an extractor is configured), feed name, category, and entry tags.

**Known hardening gaps**: the configured feed URL currently uses the shared
client directly instead of `safe_request()`, and a string-date fallback can
produce a naive timestamp that aborts the remainder of that feed. Treat feed
URLs as trusted operator configuration until those paths are hardened.

## Reddit

**File**: `src/scrapers/reddit.py`

Uses public, no-key Reddit endpoints. Subreddit listings and comments prefer `old.reddit.com` HTML because Reddit's unauthenticated JSON and RSS endpoints can intermittently block or fail:

- `GET https://old.reddit.com/r/{subreddit}/{sort}/` — subreddit posts
- `GET https://old.reddit.com/r/{subreddit}/comments/{post_id}/` — post comments
- `GET /r/{subreddit}/{sort}.json` — subreddit posts fallback
- `GET /user/{username}/submitted.json` — user submissions
- `GET /r/{subreddit}/comments/{post_id}.json` — post comments fallback
- `GET /r/{subreddit}/{sort}/.rss` — subreddit posts fallback when JSON is blocked

Subreddits and users are fetched concurrently. Comments are sorted by score, limited to the configured count, and exclude moderator-distinguished comments. Self-text is truncated at 1500 chars, comments at 500 chars.

**Config** (`sources.reddit`):

```json
{
  "enabled": true,
  "fetch_comments": 5,
  "subreddits": [
    {
      "subreddit": "MachineLearning",
      "sort": "hot",
      "fetch_limit": 25,
      "min_score": 10,
      "category": "ai-ml"
    }
  ],
  "users": [
    {
      "username": "spez",
      "sort": "new",
      "fetch_limit": 10,
      "category": "social"
    }
  ]
}
```

- `sort` — `hot`, `new`, `top`, or `rising` (subreddits); `hot` or `new` (users)
- `time_filter` — for `top`/`rising` sorts: `hour`, `day`, `week`, `month`, `year`, `all`
- `min_score` — minimum post score (subreddits only)
- `category` — optional tag for balanced digest grouping; set per subreddit or per user entry

**Rate limiting**: Detects HTTP 429 responses on JSON requests, reads the `Retry-After` header, waits, and retries once. Uses browser-like request headers for no-key public access.

**Extracted data**: title, URL, author, score, upvote ratio, comment count, subreddit, flair, self-text, top comments, and category.

## OpenBB

**File**: `src/scrapers/openbb.py`

Uses the [OpenBB Platform](https://www.openbb.co/platform) Python SDK via `obb.news.company()` to fetch company news for one or more ticker watchlists.

The scraper imports `openbb` lazily. If the optional dependency is not installed, Horizon logs a warning and skips the source instead of failing the whole run.

**Config** (`sources.openbb`):

```json
{
  "enabled": true,
  "watchlists": [
    {
      "name": "megacaps",
      "symbols": ["AAPL", "MSFT", "NVDA"],
      "enabled": true,
      "provider": "yfinance",
      "fetch_limit": 20,
      "category": "equities"
    }
  ]
}
```

- `watchlists` — each enabled watchlist triggers one `news.company()` call per run
- `provider` — OpenBB provider name for that watchlist
- `symbols` — tickers fetched together for the same provider
- `fetch_limit` — maximum rows requested from the provider
- `category` — optional metadata tag stored on each item

Behavior:

- Wraps the synchronous OpenBB SDK in `asyncio.to_thread` so the event loop stays responsive
- Deduplicates duplicate news across watchlists by article URL
- Skips malformed rows, rows without URL/title/date, and items older than the current time window
- Keeps fetching other watchlists if one provider call fails

**Credentials**: provider-specific secrets are resolved by the OpenBB SDK from its own environment variables or settings file. Horizon does not pass those values directly.

**Extracted data**: title, URL, author, published time, article body/excerpt, watchlist name, provider, category, and symbol list.

## Twitter

**File**: `src/scrapers/twitter.py` (Apify mode) and `src/scrapers/twitter_playwright.py` (Playwright mode)

Supports two scraping modes (`mode` field):
- **`apify`** (default) — Uses the [Apify](https://apify.com) platform via the `altimis~scweet` actor.
- **`playwright`** — Uses headless Playwright with exported browser cookies (see [Twitter Cookies](twitter-cookies.md)).

Apify Flow:
1. POST to `/v2/acts/{actor_id}/runs` to trigger a run
2. Poll `/v2/actor-runs/{run_id}` until status is `SUCCEEDED` or a terminal failure
3. GET `/v2/datasets/{dataset_id}/items` to retrieve results

**Config** (`sources.twitter`):

```json
{
  "enabled": true,
  "mode": "apify",
  "users": ["example_user", "another_example"],
  "fetch_limit": 10,
  "fetch_reply_text": false,
  "max_replies_per_tweet": 3,
  "max_tweets_to_expand": 10,
  "reply_min_likes": 0,
  "actor_id": "altimis~scweet",
  "apify_token_env": "APIFY_TOKEN",
  "cookie_dir": "data",
  "cookie_file_pattern": "x_cookies_*.json"
}
```

- `mode` — `"apify"` or `"playwright"`
- `users` — Twitter screen names to monitor, without the `@` prefix
- `fetch_limit` — maximum tweets to fetch per run
- `category` — optional tag for balanced digest grouping (applies to all tweets from this source)
- `fetch_reply_text` — when `true`, a second Apify run fetches reply bodies for each important tweet and appends them under `--- Top Comments ---` for AI analysis; this post-selection expansion uses Apify even when initial collection uses `playwright`, so it still requires `apify_token_env`
- `max_replies_per_tweet` — maximum reply lines per tweet (sorted by engagement score)
- `max_tweets_to_expand` — cap on reply expansion runs per pipeline cycle, to control Apify credit usage
- `reply_min_likes` — minimum likes required for a reply to be included (default: `0`)
- `actor_id` — Apify actor ID (default: `altimis~scweet`)
- `apify_token_env` — environment variable name containing the Apify API token
- `cookie_dir` / `cookie_file_pattern` — cookie directory and file glob pattern for `playwright` mode

**Authentication**: For Apify mode, set `APIFY_TOKEN` in your `.env`. For Playwright mode, export cookies as described in [Twitter Cookies](twitter-cookies.md).

**Extracted data**: tweet text, URL, author, publish time, likes, retweets, replies, views, category, and (optionally) reply-thread text appended under `--- Top Comments ---`.

## Video (YouTube)

**File**: `src/scrapers/video.py`

Ingests videos from curated YouTube channels as text. New videos are discovered via
the channel RSS feed (`https://www.youtube.com/feeds/videos.xml?channel_id=...`), so
discovery itself needs no authentication. Content is then extracted with `yt-dlp`
using a fallback ladder:

1. **Subtitles** — downloaded as VTT without downloading the video; YouTube
   auto-caption rolling duplicates are collapsed into a clean timestamped transcript
2. **Local ASR** (`asr: "local"`) — audio-only download transcribed with mlx-whisper
   (Apple Silicon)
3. **Vision fallback** (`vision_fallback: true`) — storyboard frame grids are sent
   to the configured vision model, which produces a visual summary

The first rung that yields text wins; the result plus the full video description
becomes the item content.

**Config** (`sources.video`):

```json
{
  "enabled": true,
  "mode": "inline",
  "inbox_file": "data/video-inbox.json",
  "inbox_max_age_hours": 48,
  "channels": [
    {
      "name": "Fireship",
      "channel": "@Fireship",
      "enabled": true,
      "max_videos": 3,
      "category": "dev",
      "profile": "video"
    }
  ],
  "subtitle_langs": ["en.*", "ru.*"],
  "transcript_max_chars": 12000,
  "cookies_file": "data/youtube-cookies.txt",
  "audio_cookies_file": null,
  "vision_fallback": true,
  "asr": "local"
}
```

- `mode` — `"inline"` (extract during digest run) or `"sidecar"` (read pre-processed items from `horizon-video` sidecar inbox)
- `inbox_file` / `inbox_max_age_hours` — inbox location and staleness warning threshold for sidecar mode
- `channel` — `UC...` channel id (preferred: skips the yt-dlp channel lookup),
  `@handle`, or channel URL
- `max_videos` — per-channel, per-run cap
- `cookies_file` / `audio_cookies_file` — Netscape cookie exports to bypass the
  "Sign in to confirm you're not a bot" gate on non-residential IPs
- `asr` — `"local"` (mlx-whisper) or `"off"`

**Extracted data**: title, URL, author (channel name), publish time, transcript or
visual summary, full description, and `has_transcript` metadata.

See [Video Source](video-source.md) for the anti-bot details and debugging guide.

## 4PDA (Forum Topics)

**File**: `src/scrapers/fourpda.py`

Ingests user discussion posts from specific 4PDA forum topics (such as ISP network anomalies, censorship, DPI bypass methods, and VPN protocols). Fetches forum pages using `windows-1251` character encoding and requires no authentication or API keys.

1. **Date Parsing** — Parses Russian relative and absolute dates (*«Сегодня, 14:20»*, *«Вчера, 23:26»*, *«17.08.26, 18:43»*) in Moscow time (UTC+3) and converts them to UTC.
2. **Content Sanitization** — Strips quote blocks (`quote_body`), edit reasons, dropdown menus, and user badge icons. Skips pinned rules/FAQ header posts and trivial one-word comments.
3. **Deep Links** — Assigns exact post deep-link URLs (`https://4pda.to/forum/index.php?showtopic={topic_id}&view=findpost&p={post_id}`).

**Config** (`sources.fourpda`):

```json
{
  "enabled": true,
  "topics": [
    {
      "topic_id": 1110469,
      "name": "Суверенный Интернет – обсуждение",
      "enabled": true,
      "fetch_limit": 30,
      "category": "ru-field-report",
      "profile": "censorship-watch"
    }
  ]
}
```

- `topic_id` — numeric 4PDA topic ID from URL (`showtopic=1110469`)
- `fetch_limit` — maximum posts to ingest per topic per run
- `category` — category tag (default: `"ru-field-report"`)
- `profile` — profile routing (default: `"censorship-watch"`)

**Extracted data**: title, URL (direct post link), author, publication timestamp (UTC), cleaned post body, and topic metadata.

## Telegram

**File**: `src/scrapers/telegram.py`

Ingests public channel posts through Telegram's web-preview fallbacks (`https://telegram.me/s/{channel}`, then `telegram.dog/s` and `t.me/s`). Requires no API tokens or Telegram bot credentials.

**Config** (`sources.telegram`):

```json
{
  "enabled": true,
  "channels": [
    {
      "channel": "example_channel",
      "enabled": true,
      "fetch_limit": 20,
      "category": "news",
      "profile": "tech-news"
    }
  ]
}
```

- `channel` — Telegram channel username
- `fetch_limit` — maximum messages to fetch per channel per run
- `category` — optional category tag
- `profile` — profile routing

**Extracted data**: title, post text, channel/author, publish timestamp (UTC), and category. The item URL is the first external link in the post when present, otherwise the generated `https://telegram.me/{channel}/{id}` deep link; that deep link is always retained as `metadata.msg_url`.

## OSS Insight

**File**: `src/scrapers/ossinsight.py`

Queries the OSS Insight public API for top trending repositories by star gain.

**Config** (`sources.ossinsight`):

```json
{
  "enabled": true,
  "period": "past_24_hours",
  "languages": ["All", "Python", "TypeScript"],
  "keywords": [],
  "min_stars": 5,
  "max_items": 30,
  "category": "oss",
  "profile": "tech-news"
}
```

- `period` — `"past_24_hours"` or `"past_28_days"`
- `languages` — target language list
- `keywords` — optional substring filters on repository name, description, or collection
- `min_stars` — minimum star gain threshold (default: `5`)
- `max_items` — maximum repositories returned (default: `30`)

**Extracted data**: repository name, URL, description, star gain count, language, and category.

## GDELT

**File**: `src/scrapers/gdelt.py`

Queries the key-less GDELT 2.0 DOC API (`https://api.gdeltproject.org/api/v2/doc/doc`) for recent global news matching search queries. Accepts a list of query objects (a single object is normalized to a one-item list).

**Config** (`sources.gdelt`):

```json
[
  {
    "enabled": true,
    "query": "(\"VPN blocking\" OR \"deep packet inspection\")",
    "mode": "ArtList",
    "max_records": 75,
    "timespan": "24h",
    "language": "english",
    "country": null,
    "category": "global-censorship",
    "profile": "censorship-watch"
  }
]
```

- `query` — GDELT search query string
- `mode` — GDELT API mode (default: `"ArtList"`)
- `max_records` — maximum records requested (default: `75`; GDELT caps requests at 250)
- `timespan` — optional query timespan (e.g., `"24h"`)
- `language` / `country` — optional source language and country filters

**Extracted data**: article title, URL, domain/source name, publish timestamp (UTC), and category.

## Google News

**File**: `src/scrapers/google_news.py`

Fetches Google News RSS search feeds (`https://news.google.com/rss/search`) for search queries via `feedparser`. No API key required. Accepts a list of query objects (a single object is normalized to a one-item list).

**Config** (`sources.google_news`):

```json
[
  {
    "enabled": true,
    "query": "(VPN OR DPI) (blocking OR shutdown)",
    "language": "ru",
    "country": "RU",
    "ceid": "RU:ru",
    "max_results": 100,
    "category": "ru-censorship",
    "profile": "censorship-watch"
  }
]
```

- `query` — search query string
- `language` — search language (`hl`, default `"en"`)
- `country` — search country (`gl`, default `"US"`)
- `ceid` — optional Google News CEID (auto-derived as `"{country}:{language}"` when omitted)
- `max_results` — maximum feed entries retained (default: `100`)

**Extracted data**: article title, URL, news publisher, feed publication timestamp, and category. Parsed feed tuples become aware UTC timestamps; a direct string fallback can still remain naive, and the scraper currently relies on the query time operator rather than applying a second local `since` filter (known hardening gaps).

