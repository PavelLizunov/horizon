# AGENTS.md — Guide for AI Agents Working in This Repo

This repository is a maintained fork of [Thysrael/Horizon](https://github.com/Thysrael/Horizon)
(MIT) with five major architectural additions of its own:

- a **YouTube video source** (`sources.video`) that ingests channel videos as timestamped
  transcripts, with ASR and vision fallbacks (§6);
- a **4PDA forum topic source** (`sources.fourpda`) that ingests user field reports on censorship,
  VPN protocols, and bypass techniques from Russian discussion threads (§6.2);
- a **published site** — the digest is rendered by MkDocs Material and shipped to an ingress,
  and Telegram carries only headlines that deep-link into it (§8);
- **narration** — the deployment attempts a Russian voice track per published article,
  grades it with a second model, and links only tracks that pass (§6.5);
- an **Evidence Ledger & fact-checking engine** (`verification`) — extracted core factual claims
  are verified against independent web searches, cost-accounted, and corroborated on site pages (§6.7).

The project follows **Spec-Driven Development (SDD)**: specifications, plans, and tasks in `specs/`
are the source of truth for architectural decisions and feature development (§11).

Everything below is written so an AI coding agent (or a human) can work here safely without
any outside context.

## Instruction precedence and local guides

- Direct system, developer, and user instructions take precedence over repository guides.
- The closest `AGENTS.md` to a changed file owns local rules; parent guides still apply where
  the local guide is silent.
- Every tracked content directory has a local guide. Keep those guides scoped to local ownership,
  invariants, API coupling, and narrow verification instead of copying this file.

## 1. What This Project Does

Horizon is an AI-driven news digest and intelligence pipeline:

```
fetch → URL dedup → classify/score → filter/topic dedup → enrich (LLM + web search)
    → fact-check / verify (Evidence Ledger) → digest markdown → delivery (file / webhook / email / MCP)
                                            → site pages → build/ship → narration → build/ship
                                                                              (deploy/run-daily.sh)
```

Sources: Hacker News, RSS, Reddit, Telegram, Twitter/X, GitHub, OpenBB, OSS Insight,
GDELT, Google News, **YouTube channels** (§6), and **4PDA forum topics** (§6.2).

The pipeline is provider-agnostic: any OpenAI-compatible or native SDK backend works
(Anthropic, OpenAI, DashScope/Qwen, DeepSeek, Ollama, ...). The active provider is
configured in `data/config.json` (see §4) — never hardcoded.

## 2. Repository Map

```
src/
  ai/                # provider clients, scoring, enrichment, summarization, narration text
  scrapers/          # one module per source; video.py (YouTube), fourpda.py (4PDA topics)
  extractors/        # optional full-article extraction
  processing/        # profiles engine, content selection, tools (web search)
  verification/      # Evidence Ledger claims, evidence, fetching, audit, incidents, persistence
  services/          # webhook/email delivery, search indexing, video and webhook CLIs
  mcp/               # MCP server exposing staged pipeline tools and read-only resources
  setup/             # interactive wizard, presets, source recommendations
  storage/           # config/state loading and generated site-page persistence
  models.py          # authoritative Pydantic config and serialized pipeline models
  orchestrator.py    # wires every stage together — read docs/pipeline.md first
profiles/            # per-profile prompt/config dirs (tech-news, video, censorship-watch, ...)
specs/               # Spec-Driven Development (SDD) specifications, plans, and task breakdowns
  constitution.md    # project rules, invariants, and coding standards
data/
  config.json        # REAL runtime config — GITIGNORED, never commit (may reference secrets)
  config.example.json# documented template — keep it in sync with models.py
  youtube-cookies*.txt # GITIGNORED session cookies — TOP-SECRET, never commit
tests/               # pytest suite (offline; network code is mocked)
scripts/             # dev/debug utilities (dev_check_*.py, dev_collection_status.py, etc.)
deploy/              # systemd/launchd templates + RUNBOOK.md for driving the deployed box
                     #   run-daily.sh is what systemd (or launchd) calls: pipeline, index,
                     #   build/ship, narration, build/ship — text goes live
                     #   first so speech cannot hold Telegram links on a 404
docs/                # long-form docs:
                     #   video-source.md, pipeline.md, narration.md,
                     #   verification/ (Evidence Ledger methodology and specs),
                     #   collection.md (live sources summary), checks.md
  digest/index.md    # GENERATED but tracked: a fresh clone needs it to build, so
                     #   it holds an empty-state placeholder. Any git operation on
                     #   the deployed box restores that over the real listing —
                     #   run-daily.sh regenerates it before every build
CHANGELOG.md         # what this fork added and WHY — read before "fixing" something
                     #   that looks odd; several oddities are load-bearing
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
horizon-video --hours 24        # video sidecar only (writes data/video-inbox.json)
```

### What costs real money — read before running anything

`horizon` is a paid LLM job. Output dominates the bill.
A reference run without verification: ~260 000 tokens for 11 items.
With Evidence Ledger verification enabled: adds ~40 000 – 55 000 tokens per verified item.

| Command | Cost |
|---------|------|
| `pytest` | free, offline, no API keys |
| Parser-only checks listed in `scripts/AGENTS.md` | no LLM tokens; some still use live network |
| `horizon-video` | may spend LLM tokens when vision fallback is needed |
| `horizon`, model scoring/A-B scripts, section-C scripts | model/API work; require owner approval |

Never run `horizon` to "check that it works". Start with offline tests and only run a script
after checking its cost/network class in `scripts/AGENTS.md`.

Cutting cost: the lever is **output volume**, not model choice — raise profile
thresholds, lower `digest.max_items`, or reduce enrichment blocks.

Tests (must pass before any "done" claim; all offline, no API keys needed):

```bash
pytest                          # full suite
pytest tests/test_video.py -q   # video module only
pytest tests/test_fourpda.py -q # 4PDA module only
```

There is no project-wide linter configuration; follow the style of neighboring files.
GitHub Actions (`.github/workflows/tests.yml`) runs pytest on pushes to `main` and on pull requests.

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

## 6. The Video Source

Read `docs/video-source.md` before changing anything in `src/scrapers/video.py`.
The short version:

- New videos are discovered via the **channel RSS feed** (cheap, no auth).
- Content extraction ladder: **subtitles (yt-dlp)** → **local ASR** (`mlx-whisper`,
  macOS reference) → **vision fallback** (storyboard frames summarized by the
  configured vision model, with ASR off on Linux production). First rung that produces text wins.
- YouTube actively blocks non-residential IPs. Workarounds are documented in `video.py`.
- `yt-dlp` is imported lazily inside methods, so tests run offline without touching the network.

### Invariants for Video
1. **Degrades, never raises.** Every external call is wrapped; failure means fewer transcripts, not a dead run.
2. **Degradation stays visible.** `_log_run_summary()` prints extraction stats and logs WARNING when under `min_transcript_rate`.
3. **Metadata filters fail open.** Missing duration/status does not skip items.
4. **ASR memory is released.** `_release_asr()` purges Metal buffer pool in `fetch()`'s `finally`.
5. **Tests are offline.** `VideoConfig.asr` in tests is `"off"` or mocked.

## 6.2 The 4PDA Forum Source

Read `src/scrapers/fourpda.py` before modifying forum ingestion.

- Ingests specific discussion topics (e.g. `1110469` *«Суверенный Интернет»*).
- Fetches HTML directly using `windows-1251` encoding without anti-bot blockage.
- Automatically handles Russian relative dates (*«Сегодня, 14:20»*, *«Вчера, 23:26»*, *«17.08.26, 18:43»*) converted to UTC.
- Strips quote blocks (`quote_body`), edit notes, user badge icons, and pinned FAQ headers.
- Produces individual `ContentItem` objects with deep links to specific post IDs (`&view=findpost&p=...`).

### Invariants for 4PDA
1. **Dates must parse in MSK timezone (UTC+3)** before converting to UTC.
2. **Quotes are stripped** before text scoring to avoid rating old quoted messages.
3. **Short posts (<15 chars) and rule headers are skipped** to keep digest signal high.

## 6.5 Narration

The deployment attempts a Russian voice track for each published article on supported runtimes
and links only tracks that pass grading. On Linux production, narration is skipped until
independent Linux grading exists; macOS is retained as a supported cold rollback/reference.
Read `docs/narration.md` before touching it.

Shape: `src/ai/narration.py` prepares the text (pure, tested, offline).
`scripts/dev_narrate_article.py` runs on the host in a **separate venv** (`~/tts/.venv`)
with TeraTTSv2 / `ru_f1` and Whisper grading (macOS reference).
`deploy/run-daily.sh` publishes text pages first, runs synthesis (when enabled), then ships again.

### Invariants for Narration
1. **The grader is a different model from the generator.** Whisper grades TeraTTSv2.
2. **Grade per piece, not per finished file.** Avoids long-window hallucination / dropouts.
3. **A failed check is never published.** `_speak` returns non-zero, nothing is uploaded.
4. **Chunk bounds are 120–400 characters, packed evenly.**
5. **Acronyms are unspelled by letter name** ("джи-пи-ю" vs "GPU").
6. **Files are encoded at 1.25x**, player default is 1x.

## 6.7 Evidence Ledger & Fact-Checking Verification

Read `docs/verification/` and `src/verification/AGENTS.md` before touching verification logic.

- Extracts 1–3 core verifiable factual claims from reader-visible enriched articles.
- Performs bounded targeted searches, fetches public source documents, and grades evidence stance.
- Persists versioned claim, evidence, report, public-view, and incident-ledger schemas.
- Renders type-aware reader-facing claim coverage, links only validated public sources, and suppresses operational error states.

### Invariants for Verification
1. **Public pages must not show internal error statuses.** Current `verification_error`, `check_error`, and `not_checked` states—and legacy/defensive `check_failed` inputs—must remain invisible to readers; no scary "Проверка прервана" banners belong on live articles.
2. **Article banners omit raw dollar costs and token accounting.** The public checks page currently publishes usage and estimates by explicit implementation/test/changelog contract, conflicting with older constitution/spec wording. Do not change either side silently; resolve it through an owner-approved API/policy decision.
3. **Graceful fallback on search rate limits.** If search fails or times out, the article publishes normally and operational errors stay hidden. A healthy but inconclusive check may still show a conservative coverage label.

## 7. AI Backend Notes

- Any provider works; the deployment this fork is tuned for uses an
  OpenAI-compatible gateway (DashScope/Qwen/DeepSeek) with a single `api_key_env`.
- Runtime score thresholds and category overrides live only under
  `processing.profile_settings.<profile>` in config; profile directories own prompts and content
  shape, not filtering policy (for example `category_thresholds: {"llm": 4.5, "sdd": 4.5}`).
- Vision calls reuse `ai.model` (base64 data-URI).

## 8. Deployment

The current production pipeline runs on a dedicated Debian LXC using systemd, with macOS
(Apple Silicon via launchd) retained as a supported cold rollback/reference platform.
Archive search remains separate as `horizon-elasticsearch.service` plus
`horizon-search-api.service`. See `deploy/README.md`, `deploy/RUNBOOK.md`, and `deploy/search/README.md`.

- Pipeline runtime deps: `node` (yt-dlp JS solver) and `ffmpeg`.
- Narration venv: `~/tts/.venv` (macOS reference runtime; skipped on Linux production).
- The Compose search stack is reference/local only, not current production.
- Site, search, SSH, and audio destinations are deployment-specific. Do not copy concrete
  endpoints into new code or docs; changing existing operational defaults requires owner review.

## Public APIs and compatibility

Treat these as versioned compatibility surfaces, even when implemented as Python or JSON rather
than HTTP: Pydantic config and `ContentItem` models, CLI entry points and flags, profile JSON and
prompt contracts, MCP tool/resource names and envelopes, run artifact files and schema versions,
search API responses, webhook placeholders/statuses, and published page/deep-link paths.

Before changing one of them:

1. Write or update the owning `specs/` documents with compatibility and migration behavior.
2. Prefer additive changes; never silently rename fields, statuses, tools, resources, stages, or URLs.
3. Add offline contract/regression tests and update the owning README plus local `AGENTS.md`.
4. Do not implement an API redesign from an audit finding alone; agree the target contract first.

## 9. Measurement Discipline

Findings in this repo are expected to be measured, not asserted.
- Use `mx.get_active_memory()` / `mx.get_cache_memory()` for MLX memory.
- Repeat runs before writing numbers into docs.
- Verify third-party library APIs against installed versions.

## 10. Working Norms

- Minimal diffs. No speculative abstractions; deletion beats addition.
- Every behavior change ships with a test in `tests/` (offline, mocked network).
- Keep `data/config.example.json`, `docs/`, and README sections in sync with code.
- Do not rename or reorder upstream files unnecessarily.
- Never store real hostnames, IPs, usernames, or account names in tracked files.

## 11. Spec-Driven Development (SDD)

This repository follows the **Spec-Driven Development** methodology:
- All major features and architectural changes are documented under `specs/`.
- Each feature directory in `specs/` contains:
  - `spec.md` — functional/non-functional requirements, data contracts, and user scenarios.
  - `plan.md` — technical architecture, component interactions, and testing plan.
  - `tasks.md` — executable, granular task checklist with completion states.
- The project constitution is maintained at `specs/constitution.md`.
