# AGENTS.md — Guide for AI Agents Working in This Repo

This repository is a maintained fork of [Thysrael/Horizon](https://github.com/Thysrael/Horizon)
(MIT) with three additions of its own:

- a **YouTube video source** (`sources.video`) that ingests channel videos as timestamped
  transcripts, with ASR and vision fallbacks (§6);
- a **published site** — the digest is rendered by MkDocs Material and shipped to an ingress,
  and Telegram carries only headlines that deep-link into it (§8);
- **narration** — every published article gets a Russian voice track, generated locally,
  graded by a second model, and linked from the page with a custom player (§6.5).

Everything below is written so an AI coding agent (or a human) can work here safely without
any outside context.

## 1. What This Project Does

Horizon is an AI-driven news digest pipeline:

```
fetch (scrapers) → analyze/score (LLM) → dedup/filter → enrich (LLM + web search)
    → digest markdown → delivery (file / webhook / email / MCP)
                      → site pages → build/ship → narration → build/ship
                                                        (deploy/run-daily.sh)
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
                     #   narration.py prepares text for speech — pure and tested
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
deploy/              # launchd templates + RUNBOOK.md for driving the deployed box
                     #   run-daily.sh is what launchd calls: pipeline, index,
                     #   build/ship, narration, build/ship — text goes live
                     #   first so speech cannot hold Telegram links on a 404
docs/                # long-form docs; video-source.md is the video module deep dive,
                     #   pipeline.md maps orchestrator.py's seven stages,
                     #   narration.md carries the speech measurements
  digest/index.md    # GENERATED but tracked: a fresh clone needs it to build, so
                     #   it holds an empty-state placeholder. Any git operation on
                     #   the deployed box restores that over the real listing —
                     #   run-daily.sh regenerates it before every build
CHANGELOG.md         # what this fork added and WHY — read before "fixing" something
                     #   that looks odd; several oddities are load-bearing
PLAN.md              # WORK IN PROGRESS checklist — if it exists, start there:
                     #   find the first unchecked box and continue. Mark steps
                     #   done as you finish them. Delete the file when shipped.
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

### What costs real money — read before running anything

`horizon` is a paid LLM job. A measured reference run: **259 942 tokens
(137 669 in / 122 273 out) for 11 delivered items**, ~23 600 tokens per item.
Output dominates the bill — on the reference deployment's tariff it is 2.8× the
input rate and ~71% of the cost of a run.

| Command | Cost |
|---------|------|
| `pytest` | free, offline, no API keys |
| `scripts/dev_check_*.py` | **free of LLM tokens** — they build the scraper without an AI config, so the vision rung stays off. They do hit YouTube. |
| `horizon-video` | LLM tokens **only** for videos with no transcript (vision fallback). Usually near-zero. |
| `horizon`, `horizon --source ...` | full price, every time |

Never run `horizon` to "check that it works" — run the tests, then a
`dev_check_*` script. If you genuinely need a paid run, ask the owner first.

Cutting cost: the lever is **output volume**, not model choice — raise profile
thresholds, lower `digest.max_items`, or reduce enrichment blocks. Note that
`record_usage` accounts per *provider*, not per *stage*, so per-stage attribution
is not available today; do not guess at it.

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
   MLX's Metal buffer pool — measured on an M4, ~2.5 GB back to 0, reproducibly.
   It cannot free the ~1.5 GB of model weights: `mlx_whisper.transcribe()`
   retains the model it builds and exposes no handle on it. The weights do not
   accumulate across videos. Sidecar mode is the complete fix, because the
   process exits. Do not "improve" this by reimplementing `transcribe()`.
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

## 6.5 Narration (the second thing this fork adds)

Every published article gets a Russian voice track. Read `docs/narration.md`
before touching it; that file carries the measurements, this one carries the
rules.

Shape: `src/ai/narration.py` prepares the text and is pure, tested and offline —
no models, no network. `scripts/dev_narrate_article.py` drives synthesis and runs
on the Mac in a **separate venv** (`~/tts/.venv`), because TeraTTSv2 needs
onnxruntime and transformers and neither belongs in the project's dependencies.
`deploy/run-daily.sh` publishes the text pages first, then calls both and ships
again. Narration must never delay the first publish: a cold model download plus
eight articles measured nine minutes of 404s after Telegram had already sent.

    .venv/bin/python scripts/dev_narrate_article.py --issue <id> --write-all <dir>
    ~/tts/.venv/bin/python scripts/dev_narrate_article.py --speak-dir <dir> --attach

### Invariants — do not break these without reading why they exist

1. **The grader is a different model from the generator.** Whisper transcribes
   what TeraTTS said and the result is compared with the text it was given. A
   model grading its own output prefers its own output. Duration is not a check:
   the worst file measured 204 seconds against 237 expected — inside any
   tolerance, and unusable.
2. **Grade per piece, not per finished file.** On a long file of this voice the
   transcriber drops whole thirty-second windows and reports a sound reading as
   broken. That was chased for an hour as a synthesis bug; measuring the signal
   with `astats` showed speech-level energy right through the stretch called
   empty. On the same pieces one at a time it makes no mistakes. The whole-file
   transcript thresholds are scoped to `--engine qwen`, where they were
   calibrated, and must not be re-enabled for Tera without new measurements.
3. **A failed check is not published.** `_speak` returns non-zero, nothing is
   uploaded, nothing is linked. An earlier version printed the verdict and
   published anyway, so a run that had just measured its own output as broken
   reported "7/7 narrated".
4. **Chunk bounds are a correctness property, not a preference.** 120–400
   characters, packed evenly. Whole articles in one generation gave one usable
   file in seven. Two-word inputs produced eleven seconds of noise from nine
   characters. Below a 400 ceiling pieces start falling under the floor: at 300,
   eleven do; at 200, the smallest is three characters. Change these only with a
   sweep over `data/summaries/` showing neither bound is breached.
5. **Comparison unspells acronyms before matching.** The pipeline writes
   "джи-пи-ю" so it is said correctly; a recogniser writes "GPU" straight back.
   Counting those as different took a sound article from 0.84 to 0.73. Unspell by
   letter *name*, never by splitting on hyphens — "дабл-ю" contains one.
6. **Latin stays as written.** Marking it `<en>` for TeraTTS destroys the
   reading: coverage 0.73 → 0.05, transcript returns as gibberish. Transliterating
   it wholesale was also tried, for Silero, and reverted with it.
7. **Files are encoded at 1.25x and the player's default is 1x.** The two move
   together or they compound. The stored-preference key is versioned for the same
   reason. Every duration shown to a listener is in the encoded timebase.
8. **Every published URL is fetched until it returns the whole file.** The first
   read of a new object through `r2.dev` comes back truncated at exactly 20480
   bytes — with a 200, and a Content-Length that states the full size. Reproduced
   deliberately. This warms only the edge the Mac reaches; a listener elsewhere
   can still get the short read, and the durable fix is leaving `r2.dev`.

### Settled by listening, do not relitigate without new audio

TeraTTSv2 / `ru_f1` reads the digest. Rejected, each on the same article and each
by ear: **Qwen3-TTS** (wandering intonation, threefold pace swings — QwenLM #239,
nothing on our side touched it; still reachable via `--engine qwen`, and still
better at English), **Qwen bf16** (identical faults, so quantisation was never the
cause), **Qwen 25 Hz** (does not exist publicly, under any author), **Silero v5**
(reads English badly; its Russian model has no Latin graphemes and drops those
words silently, and 13.5% of a digest is Latin), **Chatterbox Multilingual** (no
voice of its own, failed the end check outright, wrong stress and an accent),
**F5-TTS Russian** (60× slower, hangs on the first piece via its API, CC-BY-NC),
**marking stress with ruaccent** (Qwen garbles combining acutes; `+` marks are
read aloud as the word).

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

Production runs on a macOS (Apple Silicon) box via launchd — see `deploy/README.md`
for setup and `deploy/RUNBOOK.md` for operating it remotely (shell traps, health
checks, which commands cost money). The host address is deliberately absent from
this repo; it lives in the operator's local SSH config (§5).
Key facts for agents:

- The runtime needs `node` on PATH (yt-dlp's JS challenge solver) and `ffmpeg`
  (narration levels, joins and encodes with it).
- Narration runs from its own venv at `~/tts/.venv`. `mlx_whisper` shells out to
  a bare `ffmpeg`, and a non-interactive ssh session on that box has almost no
  PATH — the driver prepends `/opt/homebrew/bin` itself. `uv` is in `~/bin`, not
  on the default PATH either.
- Audio lives in Cloudflare R2 and is served through a Caddy vhost that rewrites
  `Host` to the bare bucket hostname. With a port on it, R2 aborts the body at
  exactly 20480 bytes and reports nothing.
- Local ASR needs `mlx-whisper` and ~2 GB disk for the whisper model cache; it is
  Apple-Silicon-only. On other platforms set `video.asr: "off"` and rely on
  subtitles + vision fallback.
- Logs: `logs/horizon.log` (gitignored). A healthy run ends with
  "Horizon completed successfully!" and a token-usage summary.

## 9. Measurement Discipline

Findings in this repo are expected to be measured, not asserted. Three traps
that have already produced wrong conclusions here:

- **RSS is the wrong instrument for MLX memory.** The allocator retains pages
  after a free, so `ps -o rss=` gave 378 MB on one run and 1810 MB on the next
  for identical work. Use `mx.get_active_memory()` / `mx.get_cache_memory()`.
- **A single run is not a measurement.** Both of the above came from one run
  each. Repeat before writing a number into the docs.
- **Assumptions about third-party internals must be verified against the
  installed version.** `_release_asr` was built around an `lru_cache` on
  `mlx_whisper.load_model` that does not exist in 0.4.3, and it logged a false
  WARNING on every healthy run until that was checked.

When a claim cannot be verified on the current machine (mlx does not install on
Windows, for example), say so rather than inferring it.

## 10. Working Norms

- Minimal diffs. No speculative abstractions; deletion beats addition.
- Every behavior change ships with a test in `tests/` (offline, mocked network).
- Keep `data/config.example.json`, `docs/`, and README sections in sync with code.
- Do not rename or reorder upstream files unnecessarily — this fork should stay
  merge-friendly with `Thysrael/Horizon` where practical.
- Never store real hostnames, IPs, usernames, or account names in tracked files;
  use placeholders (`YOURUSER`, `example.com`) in templates and docs.
