# AGENTS.md — Guide for AI Agents Working in This Repo

This repository is a maintained fork of [Thysrael/Horizon](https://github.com/Thysrael/Horizon)
(MIT) with one major addition: a **YouTube video source** (`sources.video`) that ingests
channel videos as timestamped transcripts, with ASR and vision fallbacks. Everything below is
written so an AI coding agent (or a human) can work here safely without any outside context.

## 1. What This Project Does

Horizon is an AI-driven news digest pipeline:

```
fetch (scrapers) → analyze/score (LLM) → dedup/filter → enrich (LLM + web search)
    → digest markdown → delivery (file / webhook / email / MCP)
```

Sources: Hacker News, RSS, Reddit, Telegram, Twitter/X, GitHub, OpenBB, OSS Insight,
GDELT, Google News, and **YouTube channels** (this fork's addition).

The pipeline is provider-agnostic: any OpenAI-compatible or native SDK backend works
(Anthropic, OpenAI, DashScope/Qwen, DeepSeek, Ollama, ...). The active provider is
configured in `data/config.json` (see §4) — never hardcoded.

## 2. Repository Map

```
src/
  scrapers/          # one module per source; video.py is the YouTube scraper
  ai/                # LLM clients, analyzer (scoring), enricher, summarizer
  processing/        # profiles engine, dedup, tools (web search)
  services/          # webhook delivery
  mcp/               # MCP server exposing pipeline stages as tools
  models.py          # ALL pydantic config models live here (Config, SourcesConfig, ...)
  orchestrator.py    # wires every stage together — read docs/pipeline.md first,
                     #   it maps the 7 stages to methods so you can skip the file
profiles/            # per-profile prompt/config dirs (tech-news, video, ...)
  video/             # profile used by the YouTube source
data/
  config.json        # REAL runtime config — GITIGNORED, never commit (may reference secrets)
  config.example.json# documented template — keep it in sync with models.py
  youtube-cookies*.txt # GITIGNORED session cookies — TOP-SECRET, never commit
tests/               # pytest suite (offline; network code is mocked)
scripts/             # dev/debug utilities (dev_check_*.py need a real config to run)
deploy/              # launchd plist template for scheduled runs on macOS
docs/                # long-form docs; video-source.md is the video module deep dive
```

## 3. Setup & Commands

Python ≥ 3.11, `uv` recommended:

```bash
uv venv && uv pip install -e ".[dev]"   # or: pip install -e ".[dev]"
cp data/config.example.json data/config.json   # then edit
cp .env.example .env                          # then fill in keys
```

Run:

```bash
horizon --hours 24              # full pipeline for the last 24h
horizon --source video          # single source (useful for debugging)
horizon-video --hours 24        # video sidecar only (writes data/video-inbox.json)
```

Tests (must pass before any "done" claim; all offline, no API keys needed):

```bash
pytest                          # full suite
pytest tests/test_video.py -q   # video module only
```

There is no project-wide linter configuration; follow the style of neighboring files.
GitHub Actions (`.github/workflows/tests.yml`) runs pytest on push/PR.

## 4. Configuration Model

- Config schema = pydantic models in `src/models.py`. Adding a source means:
  model in `models.py` → registry entry in `SOURCE_REGISTRY` → scraper in
  `src/scrapers/` → wiring block in `orchestrator.fetch_all_sources()` →
  `data/config.example.json` section → test coverage in `tests/`.
- `data/config.example.json` must stay valid against `models.py` — tests load it.
- Secrets are **environment-variable references** (`api_key_env`, `password_env`,
  `url_env`), loaded from `.env` via python-dotenv. The config file itself stores
  only the variable *name*, never the value.

## 5. Secrets Policy — Hard Rules

**NEVER commit, print, or paste into issues/PRs/logs:**

| Path | Why |
|------|-----|
| `.env` | API keys |
| `data/config.json` | live runtime config |
| `data/youtube-cookies*.txt` | YouTube session cookies = account access |
| `data/seen.json`, `data/summaries/`, `data/subscribers.json` | personal state |
| any `*cookies*`, `*.key`, `*.pem` | credentials |

All of the above are gitignored — verify with `git status` before committing.
If a secret ever lands in a commit, treat it as burned: rotate it and purge history.
Cookie files on disk should be `chmod 600`. In CI, secrets go through GitHub
repository secrets, never through tracked files.

## 6. The Video Source (this fork's core addition)

Read `docs/video-source.md` before changing anything in `src/scrapers/video.py`.
The short version:

- New videos are discovered via the **channel RSS feed** (cheap, no auth).
- Content extraction ladder: **subtitles (yt-dlp)** → **local ASR** (`mlx-whisper`,
  Apple Silicon) → **vision fallback** (storyboard frames summarized by the
  configured vision model). First rung that produces text wins.
- YouTube actively blocks non-residential IPs. The workarounds (player clients,
  cookie files, JS runtime requirements) are encoded in `video.py` comments —
  read them before "simplifying" anything there; they were each paid for in
  debugging time.
- `yt-dlp` is imported lazily inside methods, so tests run without it touching
  the network; keep it that way.

### Invariants — do not break these without reading why they exist

1. **This module degrades, it never raises.** Every external call is wrapped;
   failure means fewer transcripts, not a dead run. That is deliberate *and*
   dangerous, which is why (2) exists.
2. **Degradation must stay visible.** `_preflight()` reports missing
   runtime deps once per run; `_log_run_summary()` prints the extraction
   breakdown and promotes it to a WARNING (`Video run degraded`) when the share
   of videos yielding text falls under `video.min_transcript_rate`. If you add a
   new failure path, count it in `VideoRunStats` — an uncounted failure is an
   invisible one.
3. **Metadata filters fail open.** `_skip_reason()` drops Shorts and premieres
   using `duration` / `live_status`, but *missing* metadata never skips. A
   yt-dlp change that drops a field must not silently empty the digest.
4. **ASR memory is released in `fetch()`'s `finally`.** `_release_asr()` drops
   MLX's Metal buffer pool, which otherwise stays resident through analysis and
   enrichment (measured on an M4: 1540 MB peak, 378 MB after). mlx-whisper
   itself memoises nothing on 0.4.3, so the model-cache clearing in that method
   is version insurance, and finding no cache is silent by design.
5. **Tests are offline, including the ASR path.** `VideoConfig.asr` defaults to
   `"local"`, so any test that leaves a video without subtitles will call the
   real yt-dlp audio downloader unless it sets `asr="off"` or mocks
   `_asr_local`. The helper in `tests/test_video.py` defaults to `"off"` for
   this reason — keep new tests on that path.
6. **`mlx-whisper` lives in the `asr` extra, never in the base deps.** It is
   Apple-Silicon-only, and a plain `uv sync` prunes anything not in the
   lockfile — a hand-installed copy disappears without an error.
7. **Two modes, one module.** `sources.video.mode` is `"inline"` (extract during
   the digest run) or `"sidecar"` (read `inbox_file`, produced by the separate
   `horizon-video` CLI in `src/services/video_cli.py`). The sidecar forces
   itself back to `"inline"` internally — never remove that, or it will read the
   file it is supposed to write. Bump `INBOX_VERSION` in `video.py` whenever the
   on-disk shape changes; the reader ignores a mismatch instead of guessing.

## 7. AI Backend Notes

- Any provider works; the deployment this fork is tuned for uses an
  OpenAI-compatible gateway (DashScope-family) with a single `api_key_env`.
- Vision calls (storyboard fallback) reuse `ai.model` — it must accept
  `image_url` content parts (data-URI base64; remote URLs are unreliable).
- Token cost matters: schedule daily runs inside your provider's off-peak window
  if it has one, and keep `transcript_max_chars` / profile `content` limits in mind
  (transcripts are long; the scorer should see head+middle+tail sampling, not just
  the intro — see `profiles/video/profile.json` `content` block).

## 8. Deployment

Production runs on a macOS (Apple Silicon) box via launchd — see `deploy/README.md`.
Key facts for agents:

- The runtime needs `node` on PATH (yt-dlp's JS challenge solver), plus `ffmpeg`
  only if you add transcoding (not required today).
- Local ASR needs `mlx-whisper` and ~2 GB disk for the whisper model cache; it is
  Apple-Silicon-only. On other platforms set `video.asr: "off"` and rely on
  subtitles + vision fallback.
- Logs: `logs/horizon.log` (gitignored). A healthy run ends with
  "Horizon completed successfully!" and a token-usage summary.

## 9. Working Norms

- Minimal diffs. No speculative abstractions; deletion beats addition.
- Every behavior change ships with a test in `tests/` (offline, mocked network).
- Keep `data/config.example.json`, `docs/`, and README sections in sync with code.
- Do not rename or reorder upstream files unnecessarily — this fork should stay
  merge-friendly with `Thysrael/Horizon` where practical.
- Never store real hostnames, IPs, usernames, or account names in tracked files;
  use placeholders (`YOURUSER`, `example.com`) in templates and docs.
