# Changelog

What this fork adds on top of [Thysrael/Horizon](https://github.com/Thysrael/Horizon).
Upstream's own history is not repeated here.

The entries exist to answer one question quickly: *why is this code the way it
is?* Several of them encode findings that cost real debugging time and are not
recoverable by reading the code.

## Unreleased

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
