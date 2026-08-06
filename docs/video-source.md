---
layout: default
title: Video Source (YouTube)
---

# Video Source (YouTube)

The video source ingests videos from curated YouTube channels and turns them into
text items the regular pipeline can score, enrich, and digest. Design adapted from
[bradautomates/claude-video](https://github.com/bradautomates/claude-video) (MIT).

- **Code**: `src/scrapers/video.py`
- **Config models**: `VideoConfig` / `VideoChannelConfig` in `src/models.py`
- **Profile**: `profiles/video/`
- **Tests**: `tests/test_video.py` (offline)

## Pipeline

```
channels (config)
  └─ resolve channel id (UC... passthrough, else yt-dlp lookup)
      └─ channel RSS feed  →  new videos within the time window
          └─ per video, first content rung that works wins:
              1. subtitles            (yt-dlp, no video download)
              2. local ASR            (download audio → mlx-whisper)   [asr: "local"]
              3. vision fallback      (storyboard frames → vision LLM) [vision_fallback: true]
          └─ ContentItem (transcript + full description as content)
```

Item content = full video description + timestamped transcript (or visual summary),
truncated to `transcript_max_chars`. Items route to the profile set per channel
(default `video`).

## Configuration

`sources.video` (see `data/config.example.json` for a full example):

| Field | Default | Meaning |
|-------|---------|---------|
| `enabled` | `false` | Master switch |
| `mode` | `"inline"` | `"inline"` = extract during the digest run; `"sidecar"` = read items produced by a separate `horizon-video` process (see below) |
| `inbox_file` | `data/video-inbox.json` | Where the sidecar writes and the pipeline reads (sidecar mode only) |
| `inbox_max_age_hours` | `48` | Warn when the inbox has not been refreshed in this long. `0` disables the check |
| `channels` | `[]` | List of channel entries (see below) |
| `subtitle_langs` | `["en.*", "ru.*"]` | yt-dlp subtitle language patterns |
| `transcript_max_chars` | `12000` | Content cap per item |
| `cookies_from_browser` | `null` | Browser name to read cookies from (fragile on modern Chromium — prefer files) |
| `cookies_file` | `null` | Netscape `cookies.txt` export used for subtitles/storyboards/channel resolution |
| `audio_cookies_file` | `null` | Separate cookies export used **only** for audio downloads (see SABR below) |
| `vision_fallback` | `true` | Summarize storyboard frames when no transcript exists |
| `vision_max_frames` | `8` | Max storyboard grids sent to the vision model |
| `asr` | `"local"` | `"local"` = mlx-whisper on Apple Silicon; `"off"` = skip ASR |
| `asr_model` | `mlx-community/whisper-large-v3-turbo` | HuggingFace repo for mlx-whisper |
| `asr_max_duration_sec` | `5400` | Skip ASR above this length (a 3-hour stream VOD costs more wall clock than the rest of the run). `0` disables the guard |
| `min_duration_sec` | `120` | Skip videos shorter than this — channel feeds carry Shorts, which cost a full LLM analysis for no substance. `0` disables the filter |
| `min_transcript_rate` | `0.5` | Health floor: below this share of videos yielding text, the run logs a WARNING instead of degrading silently. `0` disables the check |
| `min_transcript_coverage` | `0.75` | Completeness floor for one transcript: its last timestamp against the video's runtime. Below it the item is flagged `partial` |

Channel entry:

```json
{
  "name": "Fireship",            // display name (optional)
  "channel": "@Fireship",        // @handle, channel URL, or UC... id (fastest, no lookup)
  "enabled": true,
  "max_videos": 3,               // per run, per channel
  "category": "dev",             // optional digest grouping tag
  "profile": "video"             // profile route
}
```

Prefer explicit `UC...` channel ids: they skip the yt-dlp channel-resolution call
entirely. Find the id on the channel's About page or in the RSS URL.

## Scoring Long Transcripts

The analyzer sees at most the profile's `content.analysis_max_chars` characters.
Transcripts easily exceed that, so `profiles/video/profile.json` sets:

```json
"content": {
  "analysis_max_chars": 12000,
  "enrichment_max_chars": 24000,
  "sampling": "head-middle-tail"
}
```

Without `head-middle-tail` sampling the scorer only reads the intro and underrates
videos whose substance starts later. Keep this block when copying the profile.

The `video` profile threshold is intentionally lower than news profiles (5.0):
channels are pre-curated, and the scorer is naturally strict about conversational
transcript style.

## YouTube Anti-Bot Gotchas (read before debugging)

YouTube gates non-residential IPs (VPS, VPN egress) behind "Sign in to confirm
you're not a bot". Every workaround below exists because the naive approach failed;
do not remove them while "cleaning up".

1. **Player clients.** Subtitles/storyboards use `player_client: ["tv", "android"]`
   which usually passes the gate. Channel resolution uses the same pair.

2. **SABR experiment.** Some (account, IP) pairs land in a streaming experiment
   that hides all audio formats. Two consequences:
   - Audio downloads set `player_client: ["tv_embedded"]`. **Measured on
     2026-08-06 with yt-dlp 2026.07.04, this setting is now a no-op**: yt-dlp
     answers `Skipping unsupported client "tv_embedded"` and falls back to its
     defaults, and 12 https audio formats appear anyway. What actually earns
     them is fresh cookies plus the JS runtime and EJS solver in point 3. The
     setting is kept for older yt-dlp versions; do not treat it as load-bearing.
   - If the main account is in the experiment, export cookies from a *different*
     Google account and point `audio_cookies_file` at them. Note that when both
     jars were re-exported, **both** worked for audio — the account split may no
     longer be needed, it is kept as cheap insurance.

   **Dubbed tracks.** Videos can carry an English dub alongside the original;
   the reference video exposes `[ru] Russian original (default)` and `[en-US]`
   variants of every audio format. `ba/bestaudio` selected the Russian original,
   because yt-dlp prefers the track YouTube marks `(default)`. Worth knowing if
   a transcript ever comes back in the wrong language.

3. **JS challenge.** Audio extraction requires yt-dlp's JS runtime support:
   `js_runtimes={"node": {}}` (a dict, not a list — the Python API does not
   autodetect runtimes) and `remote_components: ["ejs:github"]`. `node` must be on
   PATH. Without these, audio formats stay hidden even with good cookies.

4. **Cookies.** Modern Chromium encrypts cookies with app-bound DPAPI keys that
   yt-dlp cannot read, so `cookies_from_browser` usually fails on Windows. Export a
   Netscape-format `cookies.txt` with a browser extension instead and use
   `cookies_file`. Cookies expire — re-export when subtitle fetches start failing
   with bot-gate errors. Store cookie files `chmod 600`, never commit them.

5. **Storyboards survive everything.** Even when all playable formats are blocked,
   the `sb0` storyboard usually downloads. yt-dlp writes mhtml parts as **raw
   binary, not base64** — parsing must operate on bytes (`_parse_mhtml_frames`).

6. **Vision models cannot fetch YouTube URLs.** DashScope-family backends fail to
   download remote videos/images from YouTube. Frames are sent as base64 data URIs.

## Inline vs Sidecar

`mode: "inline"` (the default) runs the whole ladder inside the digest run. It
is simpler, needs one scheduled job, and is the right choice while things work.

`mode: "sidecar"` splits the source in two:

```
horizon-video   →  data/video-inbox.json  →  horizon (digest run)
 yt-dlp, cookies,      atomic JSON,            just reads the file
 whisper, node         schema-versioned        no node/ffmpeg/mlx needed
```

Use it when the video half starts costing you the digest:

- **Blast radius.** Expired cookies, a YouTube change, or a wedged yt-dlp can
  no longer slow down or destabilise the digest run — worst case the digest has
  no video section that day.
- **Wall clock.** A long ASR pass runs on its own schedule instead of holding
  the pipeline's `asyncio.gather`.
- **Placement.** The heavy job can live on the Apple Silicon box (ASR, cookies,
  residential IP) while the digest runs anywhere.
- **Retries.** Re-running `horizon-video` is cheap and touches no LLM tokens.

The cost is a second scheduled job and a file that can go stale — which is why
the reader warns about staleness rather than trusting it silently.

```bash
horizon-video --hours 24          # writes the inbox; run this before the digest
horizon --hours 24                # reads it, because mode is "sidecar"
```

`horizon-video` always scrapes for real: it forces `mode: "inline"` internally,
so pointing it at a sidecar config cannot make it read the file it is meant to
produce. Deploy both jobs with `deploy/horizon-video.launchd.example.plist` and
`deploy/horizon.launchd.example.plist` — schedule the video job first.

### What the reader does when the inbox is wrong

Every case degrades to "no video items this run" and logs a WARNING; none of
them raise:

| Inbox state | Behaviour |
|-------------|-----------|
| missing | warn (`does not exist`), no items — the sidecar job is probably not running |
| unparsable JSON | warn (`unreadable`), no items |
| `version` mismatch | warn, no items — re-run `horizon-video` after upgrading rather than guessing at an old shape |
| one malformed item | drop that item, keep the rest, warn with the count |
| older than `inbox_max_age_hours` | warn (`stopped running`) **and still use it** — stale beats empty. Note there is no cross-run dedup in this project; what limits re-emission is the time-window filter applied on read |

Items older than the run's time window are filtered on read, so a large inbox
never re-floods the digest. The sidecar's own `VideoRunStats` travel inside the
file, so the degradation warning described below still fires in the digest log
even though the work happened in another process.

## Observability — the module degrades, it does not fail

Every failure path here is caught and logged: a dead cookie jar, a missing
`node`, a YouTube change. The pipeline keeps running and still emits items —
just with descriptions instead of transcripts. In the digest that is
indistinguishable from a quiet week, so the module reports its own health.

**Preflight.** Once per run, before any channel is touched, the scraper checks
`node` and `ffmpeg` on PATH, that the configured cookie files exist, that
`mlx_whisper` is importable when `asr: "local"`, and that an AI config reached
the scraper when `vision_fallback` is on. Each problem is one WARNING line
prefixed `Video preflight:`.

**Run summary.** Every run ends with a breakdown of which rung produced the text:

```
Video run: 9 videos: 7 subtitles, 1 ASR, 0 vision, 0 description-only, 1 skipped, 0 failed
```

The line is promoted to a WARNING starting with `Video run degraded` on any of
three triggers:

1. **Any bot-gated call.** YouTube answered "Sign in to confirm you're not a
   bot", which has one cause and one fix: the cookies expired. Counted as
   `bot_gated` and reported regardless of how many videos were seen — channel
   resolution itself can be gated, leaving zero videos to count.
2. **Nothing yielded text**, with at least one graded video. Total extraction
   failure is conclusive even on a sample of one.
3. **The rate fell below `min_transcript_rate`** with at least 3 graded videos.

Trigger 3 alone is not enough in practice: a curated channel set often produces
only one or two videos a day, which would keep a rate check permanently silent
while the source quietly returns descriptions. Triggers 1 and 2 exist because
of exactly that, observed in production.

Note what is *not* checked: preflight verifies the cookie file **exists**, not
that YouTube still accepts it. A dead jar looks perfectly healthy on disk —
trigger 1 is the only thing that catches it.

### Is the transcript complete?

A transcript that stops a third of the way in looks exactly like a short one to
everything downstream. `transcript_coverage()` compares the last `[MM:SS]` cue
against the runtime from metadata; below `min_transcript_coverage` the item is
counted `partial`, logged with a WARNING, and the ratio is stored in
`metadata["transcript_coverage"]`. Typical causes: subtitles published for only
part of a video, or an ASR pass cut short. Missing duration or timestamps yield
`None`, which never counts as a fault.

This is separate from the *rate* check above: rate asks "did videos produce
text at all", coverage asks "is this one text the whole video".

### Truncation keeps the ending

`transcript_max_chars` caps item content, and a long video overruns it easily —
a 21-minute talk transcribes to ~25 000 characters against a 12 000 cap. The
transcript is therefore **sampled head-middle-tail, not prefix-cut**. A raw
slice would end the item around minute eight and the analyzer's own
head-middle-tail sampling could not recover it: truncation happens here, in the
scraper, before the profile's `content` limits ever apply. The excerpt markers
(`[Opening excerpt]` / `[Middle excerpt]` / `[Closing excerpt]`) survive into
the prompt so the model knows it is reading a sample.

The counters live on `scraper.last_run_stats` (`VideoRunStats`) for scripts and
tests. Per item, `metadata["content_source"]` records the rung that won —
`subtitles`, `asr`, `vision`, or `description` — which is the only way to tell a
real transcript from a description after the fact.

```bash
grep 'Video preflight:' logs/horizon.log
grep 'Video run'        logs/horizon.log
uv run python scripts/dev_check_video_fetch.py    # same numbers, on demand
```

## What Gets Skipped

Channel RSS feeds are not just long-form uploads. Two classes are dropped before
they reach the LLM (counted as `skipped`, not `failed`):

- **Shorts** — anything under `min_duration_sec`. They cost a full analysis pass
  and almost never carry substance.
- **Premieres and running livestreams** — `live_status` of `is_upcoming` or
  `is_live`. There is nothing to transcribe yet. Finished VODs (`was_live`) are
  ordinary videos and are kept.

Both checks read `duration` / `live_status` from the yt-dlp metadata that the
subtitle call already returns, so neither costs an extra request. Both **fail
open**: if the field is missing, the video is kept. A yt-dlp change that drops a
field must not silently empty the digest.

## ASR Notes

- `mlx-whisper` runs on Apple Silicon only; on other platforms set `asr: "off"`
  (cloud ASR is not wired up: it needs a provider endpoint with an ASR model).
  Install it through the extra — `uv sync --extra asr` — never by hand: a later
  plain `uv sync` prunes packages missing from the lockfile and would turn ASR
  off with no error.
- Model downloads on first use (~2 GB cache under `HF_HOME`, default
  `~/.cache/huggingface`). Language is auto-detected.
- A 20-minute video transcribes in roughly a minute on an M4 (measured: 1264 s
  of audio in ~90 s, 14× realtime).

### Model choice — benchmarked, do not redo this blindly

`whisper-large-v3-turbo` mangles English technical terms inside Russian speech:
on the reference video "Claude Code" comes out as `код-код` (11×), "Codex" as
`кодекс` (15×), and **neither term is ever written in Latin script**. Two
alternatives were measured on 2026-08-06 and both were rejected:

| Option | Result |
|--------|--------|
| **Parakeet** (`parakeet-tdt-0.6b-v3` via `parakeet-mlx`) | 2.2× faster, but `код-код` 11→12 and `промт` 1→3, and it keeps *fewer* Latin tokens overall (80 vs 91). Higher MLX peak memory at every workable chunk size, 2.39 GB on disk vs whisper's 1.54 GB, requires `chunk_duration` for long audio, and leaks literal `<unk>` tokens into the text. Handy's 478 MB figure is a quantized non-MLX build with no MLX equivalent. |
| **`initial_prompt` glossary biasing** | Cosmetic gains (`код-код` 11→10, `кодекс` 15→14) and one clear regression: `промт` went 0→11 despite the glossary containing the correct "промпт". |

Two independent architectures producing the same Cyrillic rendering at the same
timestamps is strong evidence the cause is **acoustic** — the speaker pronounces
these terms with Russian phonetics and both models faithfully transcribe what
they hear. No ASR swap fixes it. If it needs fixing, the answer is a
deterministic glossary post-pass over the finished transcript, which works
identically on any model's output.
- Videos longer than `asr_max_duration_sec` skip ASR and fall through to the
  vision rung or description.
- **Memory.** Measured on an M4 with `large-v3-turbo`, using MLX's own counters
  (`mx.get_active_memory()` / `mx.get_cache_memory()` — RSS is unreliable here,
  the allocator holds pages after a free):

  | Point | active | cache |
  |-------|--------|-------|
  | baseline | 0 MB | 0 MB |
  | after `transcribe()` | 1543 MB | 2566 MB |
  | after `_release_asr()` | 1543 MB | **0 MB** |
  | after a second transcribe | 1543 MB | 2560 MB |
  | after the second release | 1543 MB | **0 MB** |

  So `_release_asr` reliably returns the ~2.5 GB buffer pool, and that is the
  larger number. It does **not** free the ~1.5 GB of model weights: those stay
  live because `mlx_whisper.transcribe()` keeps a reference to the model after
  it returns. The memory is not lost — loading the model directly and dropping
  the reference (`del model; gc.collect(); mx.clear_cache()`) takes active back
  to 0 MB — but there is no supported handle on the model that `transcribe()`
  builds internally. Note the weights do not accumulate: a second transcription
  in the same process still ends at 1543 MB, not 3 GB.

  **If holding 1.5 GB through the LLM stages matters, use sidecar mode.**
  `horizon-video` exits when it is done, so the OS reclaims everything and the
  digest process never loads whisper at all. That is the only complete answer;
  no in-process cleanup beats process exit.

  mlx-whisper 0.4.3 memoises nothing on `load_model`, so there is no model cache
  to drop and none is expected; some releases have carried an `lru_cache` there,
  which `_release_asr` clears when it finds one. Its absence is normal and
  silent. What *does* warn is MLX exposing no `clear_cache` at all.

## Debugging Scripts

All run from the repo root with a valid `data/config.json` + `.env`:

```bash
python scripts/dev_check_video_fetch.py     # full fetch() over all enabled channels
python scripts/dev_check_one_video.py URL   # subtitles → vision fallback for one video
python scripts/dev_check_asr.py             # audio download + mlx-whisper on a fixed video
python scripts/dev_check_video_score.py     # run one video through the LLM scorer
```

Typical failure triage:

| Symptom | Likely cause |
|---------|--------------|
| `Video run degraded` in the log | start here — the rest of this table narrows it down |
| `N bot-gated` / `re-export the YouTube cookies` | the jar expired — YouTube rejects it even though the file exists. Confirm and fix per `deploy/RUNBOOK.md` |
| "Sign in to confirm you're not a bot" | same thing, seen raw from yt-dlp |
| audio download produces no files | SABR experiment — try `audio_cookies_file` from another account |
| `Channel resolve failed` | handle changed / yt-dlp outdated — pin `UC...` id instead |
| subtitles fine but content looks like intro only | missing `content` block in the profile (§Scoring) |
| `Video preflight: node is not on PATH` | launchd `PATH` misses node — scheduled runs ignore your shell profile |
| `Video preflight: ffmpeg is not on PATH` | Homebrew installs to `/opt/homebrew/bin`; add it to the plist `PATH` |
| `Video preflight: mlx-whisper is not installed` | expected off Apple Silicon (set `asr: "off"`); on a Mac, a plain `uv sync` pruned it — re-run `uv sync --extra asr` |
| `Video preflight: cookies_file points at a missing file` | path is relative to the working directory; launchd sets it via `WorkingDirectory` |
| every item is `description-only` | subtitles blocked *and* ASR unavailable — check the preflight lines first |
| fewer items than expected, `skipped` is high | Shorts/premieres filtered by `min_duration_sec` — lower it if that is wrong for the channel |
| whisper keeps ~1.6 GB after the video stage | `_release_asr` logged a WARNING — mlx-whisper moved its `load_model` cache |
