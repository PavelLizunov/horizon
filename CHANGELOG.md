# Changelog

What this fork adds on top of [Thysrael/Horizon](https://github.com/Thysrael/Horizon).
Upstream's own history is not repeated here.

The entries exist to answer one question quickly: *why is this code the way it
is?* Several of them encode findings that cost real debugging time and are not
recoverable by reading the code.

## Unreleased

### Narration — every article gets a voice, and something checks it

The digest is read aloud in Russian by **TeraTTSv2** (`ru_f1`), locally, as part
of the daily job. Text preparation lives in `src/ai/narration.py` — pure, tested,
offline. Synthesis runs from a separate venv on the Mac. `deploy/run-daily.sh`
calls both between the pipeline and the site build, because attaching a player
edits the markdown that mkdocs then reads.

The reason there is a checking layer at all: **speech models fail silently.** A
file exists, its duration is plausible, and the reading stopped a third of the
way in. The worst example measured 204 seconds against 237 expected — inside any
tolerance anyone would set, and unusable. So a *different* model transcribes what
was said and it is compared with the text that was sent. An article that fails is
not uploaded and not linked.

What that discipline caught, in order of how much time each cost:

- **The grader itself, twice.** Whole-word coverage was the gate first; complete
  takes topped out at 0.92 because a recogniser mishears, so it never separated
  good from broken. Later, whole-file transcription of the new voice dropped
  entire thirty-second windows and reported sound readings as broken — chased for
  an hour as a synthesis bug before `astats` showed speech-level energy right
  through the stretch called empty. Grading runs per piece now, where the same
  transcriber makes no mistakes.
- **A threshold that outlived its reasoning.** 0.75 was derived from articles of
  three to five pieces, where a lost piece cost twenty points. Pieces became 400
  characters and articles nine to fourteen of them; a lost piece now costs seven,
  inside the range mishearing covers. The exact check is the duration arithmetic.
- **Endings cut off.** Trimming trailing babble ran at 1.5s of quiet and cut at
  the transcriber's last timestamp, which is an estimate: on one article it
  landed past the end of the file and took the final word with it. Now 4s of
  quiet before trimming, a second of margin, and 2s of deliberate silence after.
- **Numbers.** 63 distinct tokens still held digits after preparation, in 92
  places — sentence-final numbers (the lookahead blocked on any period), versions
  and prices (no rule at all), and HTML entities that survived two escaping
  passes. Digits reach the model as digits and get read in another language.
- **A cache that made a truncation permanent.** The first read of a new object
  through `r2.dev` returns exactly 20480 bytes with a 200 and an honest
  Content-Length. Reproduced deliberately. Pages declare the audio immutable for
  a year, so a browser that saw the short copy kept it. Publishing now fetches
  what it published until the bytes match.

Chunk bounds (120–400 characters, packed evenly) and the 1.25× encode are
correctness properties with measurements behind them; `AGENTS.md` §6.5 lists
them as invariants, and `docs/narration.md` carries the numbers and the models
that were tried and rejected.

### Visual system v3 — the generator now emits what the CSS was written for

The v2 stylesheet described components the generator never produced, so most
of it was dead. An audit of the four published screens found twelve defects;
these are the eleven that were real. (The twelfth — "the search page is
empty" — was a false positive: the page reads empty to a text extractor
because its content is an `<input>` and a script.)

- **The heading no longer sends the reader away.** It was
  `# [title](original) ⭐️ 8.0/10`: a reader clicking what looked like the
  article's own name left the site without seeing the analysis the page
  exists for. The heading now carries the title alone, the score is its own
  `span.hz-score`, and the source link moved into the byline named by its
  domain. This also fixes the permalink — with the score inline the anchor
  came out `#amd-taalas-8010`, so rescoring an article changed its address.
- **The byline moved above the lede** and gained icons and the source link.
  It used to sit under four sentences of summary, so the reader was well
  into the text before anything said where the text came from.
- **Page type is declared, not inferred.** `article_site_markup()` wraps the
  body in `div.hz-page--article`. v2 hung the whole article treatment off
  `:has(.hz-byline)`, which meant a page that happened to lack a byline
  rendered as plain typography, silently — as the republished archive did.
- **Issue lists are `ul.hz-list`.** They were plain `- [title](x.md) ⭐️ 8.0/10`
  rows: seven identical stars, the only colour on a monochrome page, encoding
  nothing. A 4.0 and an 8.0 were set with identical weight. Rows now carry
  `data-tier`, a meter and the source domain.
- **Score scale renormalised to 4…10, tiers at 8.0/6.0.** Measured, not
  chosen: 2026-08-07 ran 4.0…8.0 in whole points, so the previous floor of 5
  clipped a real 4.0 to nothing and the 8.5 `high` threshold never fired once
   — the whole issue rendered mid and low.
- **Archive rows show a date and an article count** instead of the raw
  directory name, `2026-08-07-ru`, which made every row look identical.
- **Tool citation ids are stripped.** `[tool-2-1]` and friends reached the
  published text; they name internal calls no reader can follow. Matched in
  both raw and markdown-escaped form, since frozen summaries carry the latter.
- **Tags render as `ul.hz-tags`.** The pill belongs to `.hz-tag` alone —
  styling `code` for it, as v2 did, also caught every command and path the
  digest quotes in prose (15 in the archive: `brew doctor`, `uvx`,
  `/v1/chat/completions`…).
- **Cyrillic heading anchors.** The default slugify produced `#_1`…`#_4`:
  unreadable, and positional, so reordering an article's sections repointed
  every link into it. `pymdownx.slugs.slugify` keeps the letters.
- **A way out of an article** (`nav.hz-pager`) and one name for the archive
  in the nav, the page heading and the home-page button.
- **Search page rebuilt to the §13 contract**, including the `.hz-empty`
  states for no hits and for an unreachable index.

Operational finding from the same session: the Mac rebooted, Docker Desktop
does not start at login, and the Mac's DHCP lease moved `.246 → .247` while
the ingress proxied `/api/search` at a hard-coded `.246`. Archive search was
down and nothing reported it. `deploy/search/README.md` now says to pin the
address.

### Per-article pages, reading-first site, Elasticsearch search

Follow-up to the site/Telegram split, driven by live use: a headline link
landed readers in the middle of one long combined page, and the Material
default formatting was rejected as cluttered.

- **One page per article.** `DailySummarizer.build_article_pages()` renders
  each item under `digest/{date}-{lang}/{slug}.md` plus an issue index. The
  slug is the existing `item-{profile}-{index}` anchor minus its prefix —
  one derivation shared by the site, the TOC and the Telegram headline
  links, so the deep-link contract cannot drift. `publish_site_pages()`
  replaces `publish_site_page()`.
- **Site is the digest, nothing else.** The documentation pages (Telegram
  delivery, profiles, cookies, scoring…) are excluded from the published
  site via `exclude_docs`; they stay in the repo for GitHub. The owner's
  words: that material on the public site is "куча дополнительной ненужной
  информации".
- **Reading-first skin** (`docs/assets/horizon-digest.css`): system fonts,
  monochrome + one accent, 68ch measure, no sidebars. `article_site_markup()`
  restructures article pages site-only (the shared renderer is untouched):
  `**「Контекст」**` bold runs become `##` section headings, the glued-on score
  becomes a badge span, the byline is muted, the inter-item `---` is dropped.
- **No Google Fonts.** Material's default stylesheet link is render-blocking;
  with the CDN unreachable the page rendered blank. `font: false` + system
  stack.
- **ru chrome labels.** A ru digest fell back to the en label table
  ("References", "Tags"); it read as a bug. `LABELS["ru"]` added.
- **Elasticsearch archive search.** `src/services/search.py` (httpx, no
  client library) upserts one document per delivered article per run;
  `deploy/search/` runs single-node ES (512 MB heap, localhost-only) plus a
  stdlib read-only shaping API that Caddy proxies at `/api/search`. The
  browser never reaches ES. `scripts/dev_reindex_archive.py` backfills the
  pre-search history from `data/summaries/` with the same issue-scoped ids,
  so reindexing is idempotent. Indexing failure degrades the run with a
  warning — it never stops delivery.

### Publishing: static site + Telegram headlines

The digest is 38 461 characters and Telegram's cap is 4 096, so the full text
can never be sent there — and every unsupported tag it contains (`<details>`,
`<ul>`, `<li>`, headings, `<a id>`) makes Telegram reject the whole message
rather than degrade it. The split: full digest to a **MkDocs Material** site,
**headlines** to Telegram, deep-linked into it.

- `StorageManager.publish_site_page()` replaces 40 lines of inline Jekyll copying
  in `orchestrator.py` that **published nothing** — it wrote to a gitignored path
  while the workflow only fired on committed changes.
- Digest pages carry `search: exclude: true`. A year of them measured 35 MB of
  `search_index.json` (4.6 MB gzipped) downloaded on first search; documentation
  stays indexed, digests do not.
- `mkdocs.yml` uses `exclude_docs` rather than deleting upstream's Jekyll files,
  and `validation: anchors: ignore` — the digest TOC links to raw `<a id>`
  anchors that are not heading ids, which is the deep-link contract itself.
- `delivery: "headlines"` builds from `build_view()`, never from rendered
  markdown, so unsupported tags are structurally impossible rather than filtered.
  Chunked at 3 900 characters: an 11-item day fits one message, a real 30-item
  digest needs two.

*Why no `platform: "telegram"`?* `generic` already recognises Telegram's error
shape. `delivery` is the axis that means "how many messages and what is in
each"; `platform` is not.

*Why not Material's blog plugin?* It derives page URLs from title slugs, and the
headline links must be constructible before the page exists.

### AI layer — guards that now check their own outcome

Three defects of one shape: a limit or a guard applied where its failure is
invisible downstream.

- **The language-leak retry never verified itself.** `enricher.py` detected CJK
  in non-CJK output, regenerated the artifact once, and used the result
  unconditionally. If the retry also leaked, Chinese shipped into a Russian
  digest silently. Production logs showed ~8 leak events per run, so the base
  rate was high; shipped digests happened to be clean. The retry is now
  re-checked and a persistent leak logs a distinct `persists after retry`
  warning. Still one retry, still no raise — the defect was the missing
  verification, not the retry policy.
- **LLM output truncation was never detected.** `finish_reason` / `stop_reason`
  appeared nowhere in `src/ai/`. A response that hit `max_tokens` came back cut
  off, failed all five JSON repair strategies in `ai/utils.py`, and surfaced as
  "response was not a JSON object" — a diagnosis that sends you to fix the
  prompt when the fix is to raise `max_tokens`. `_warn_if_truncated` now runs
  next to `record_usage` for Anthropic (`max_tokens`), OpenAI and Azure
  (`length`) and Gemini (`FinishReason.MAX_TOKENS`, enum-unwrapped).
- **Three invisible hardcodes** — `content[:2000]` for profile routing,
  `comments[:1500]` in analysis, `comments[:2000]` in enrichment — are now
  `ProfileContent` fields (`classification_max_chars`,
  `analysis_comments_max_chars`, `enrichment_comments_max_chars`) with defaults
  equal to the old constants, so behaviour is unchanged until a profile opts
  in. Routing uses the *default* profile's budget, since it runs before a
  profile is chosen. For Reddit and Hacker News the discussion is often worth
  more than the post, and that ceiling was previously unreachable.

### Video source — observability

The video scraper catches every external failure and degrades to
description-only. That is deliberate: one dead channel must not end a run. The
cost is that expired cookies or a YouTube change look exactly like a quiet news
week. These changes make the difference visible.

- **Preflight** (`_preflight`) checks `node`, `ffmpeg`, cookie-file existence,
  `mlx_whisper` importability and the presence of an AI config — once per run,
  before any channel is touched. Each problem is one `Video preflight:` WARNING.
- **Run summary** (`VideoRunStats`, `_log_run_summary`) records which rung of
  the extraction ladder produced each item and prints a breakdown. Promoted to
  a `Video run degraded` WARNING on any of three triggers: a bot gate, zero
  extraction with at least one graded video, or the transcript rate falling
  under `min_transcript_rate`.
- **Bot-gate detection** (`_is_bot_gate`, `_note_ytdlp_error`) recognises
  YouTube's "Sign in to confirm you're not a bot" specifically. It has one cause
  and one fix, and it is reported regardless of sample size — channel resolution
  itself can be gated, leaving zero videos to count.
- **Transcript completeness** (`transcript_coverage`) compares the last `[MM:SS]`
  cue against the runtime from metadata. Partial subtitles and an ASR pass that
  died halfway both look like a perfectly good transcript downstream.
- Item metadata carries `content_source`, `duration` and `transcript_coverage`.

*Why three degradation triggers and not just the rate?* A curated channel set
yields one or two videos a day. A rate check needs a handful of videos before it
means anything, so on its own it would have stayed silent forever.

*Why does preflight not validate the cookies?* Because it cannot without
spending a request. Presence is checked cheaply at startup; validity is caught
by the bot-gate counter during the run. A dead jar looks perfectly healthy on
disk — that gap is the reason the counter exists.

### Video source — correctness and cost

- **ASR memory.** `_release_asr()` drops MLX's Metal buffer pool in `fetch()`'s
  `finally`. Measured on an M4 with `large-v3-turbo`: ~2.5 GB of buffer cache
  returned, reproducibly. It cannot free the ~1.5 GB of model weights —
  `mlx_whisper.transcribe()` retains the model it builds and exposes no handle
  on it. Sidecar mode is the complete fix, because the process exits.
- **Shorts and premieres are skipped** before reaching the LLM
  (`min_duration_sec`, `live_status`). Both filters fail open on missing
  metadata: a yt-dlp change that drops a field must not silently empty the
  digest.
- **ASR is skipped above `asr_max_duration_sec`** so a multi-hour stream VOD
  cannot consume the whole run.
- **Long transcripts keep their ending.** `transcript_max_chars` used to be a
  raw prefix slice. Measured on a 21-minute talk: 27 514 characters of content
  against a 12 000 cap meant everything after `[08:15]` was discarded, and the
  profile's head-middle-tail sampling could not compensate because truncation
  happens upstream of it. The transcript is now sampled with `select_content`.
- **Storyboard frames are sampled across the video**, not taken from the front,
  so a long video is not described from its intro alone.
- Naive feed timestamps are normalised; a naive/aware comparison used to take
  the whole channel down.

### Video source — sidecar mode

`sources.video.mode: "sidecar"` splits the source in two: the `horizon-video`
CLI does the fragile, slow half (yt-dlp, cookies, whisper) and writes an atomic,
schema-versioned inbox; the digest run only reads that file and needs no `node`,
`ffmpeg` or `mlx`. Every malformed-inbox case degrades with a WARNING rather
than raising. See `docs/video-source.md`.

### Packaging

- `mlx-whisper` moved into an `asr` extra, marked `darwin`/`arm64`. A plain
  `uv sync` prunes anything not in the lockfile, which had silently removed a
  hand-installed copy in production and disabled ASR with no error.

### Documentation

- `docs/pipeline.md` — maps `orchestrator.py`'s seven stages to methods, so an
  agent can skip a 950-line file. Also records why it is deliberately not split
  into stage modules.
- `deploy/RUNBOOK.md` — operating the deployed box remotely: shell traps, which
  commands cost real money, diagnosing expired cookies.
- `docs/video-source.md` — inline vs sidecar, the degradation triggers, ASR
  memory behaviour, and an expanded triage table.

## Earlier

- `2602fd5` — the YouTube video source itself: RSS discovery, yt-dlp subtitles,
  local ASR via mlx-whisper, storyboard vision fallback.
- `1c1bed5` — regenerate enriched artifacts when CJK leaks into non-CJK output.
- `6bd7dab` — Russian display names; fact-check and deep-dive enrichment blocks.
- `a362f2c` — pin `mcp<1.27`; newer releases drop `mcp.server.fastmcp`.
