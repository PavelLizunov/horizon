# AGENTS.md — Scripts Directory (`scripts/`) Guide

This file defines rules and guidelines for working in and using scripts under `scripts/`. Global project rules and overall architecture live in the root [`AGENTS.md`](../AGENTS.md).

## 1. Instruction Precedence & Directory Boundaries

- Direct system, developer, and user instructions take precedence over directory rules.
- On conflicts between guide files, this nested `scripts/AGENTS.md` wins for work under `scripts/`.
- Keep rules concise and specific to `scripts/` without duplicating root guidelines.
- **No Script Modifications**: Do not edit scripts in `scripts/` unless explicitly requested within the task scope.

## 2. Classification of Scripts

Scripts in `scripts/` serve distinct development, testing, setup, and operational purposes. AI agents must observe network, cost, and hardware boundaries before executing any script.

### A. Offline / Free Utility & Analysis Scripts
These make no network or paid-model calls. They are not uniformly read-only: status/collection tools write generated docs, and config utilities may read or rewrite ignored live state. Inspect arguments first and use scratch paths or backups where supported:

- `dev_evaluate_verification.py`: Evaluates Evidence Ledger adversarial policy corpus.
- `dev_verification_status.py`: Summarizes verification runs and updates site verification pages.
- `dev_collection_status.py`: Renders active source collection scope into `docs/collection.md`.
- `dev_republish_archive.py`: Republishes frozen digest archives into article site pages.
- `dev_inspect_config.py` / `dev_inspect_verification.py`: Inspects `data/config.json` structure or verification ledgers.
- `check_mcp.py`: Validates local MCP config loading and metrics without starting a network fetch.
- `dev_add_channels.py` / `dev_add_fourpda_config.py` / `dev_apply_user_updates.py` / `dev_tune_config.py`: Local configuration manipulation utilities.

### B. Network Scraper & API Checks (No LLM Billing)
Fetches raw HTML, RSS feeds, or model metadata over the network, but consumes **no paid LLM tokens**:

- `dev_check_video_fetch.py`: Smoke-tests YouTube scraper (yt-dlp subtitles/RSS) without AI calls.
- `dev_check_4pda.py` / `dev_check_4pda_raw.py` / `dev_check_4pda_rss.py` / `dev_check_4pda_rss_content.py` / `dev_check_fourpda_live.py` / `dev_test_4pda_parser.py`: Tests 4PDA topic HTML/RSS parsing against live endpoints; despite its name, `dev_test_4pda_parser.py` performs live URL fetches.
- `dev_check_new_channels.py`: Validates YouTube RSS feeds for new channels.
- `dev_list_opencode_models.py`: Queries the gateway model-list endpoint; it does not send completions.

### C. LLM Utility & Benchmark Scripts (STRICT: REQUIRES OWNER APPROVAL)
These send model-completion requests. Some target models named `*-free`, but they still require credentials and live provider access; other calls may bill by output volume:

- `dev_check_free_models.py`: Sends `Respond with OK` completions to each nominally free OpenCode Zen model; model naming does not make it offline.
- `dev_test_json_models.py`: Sends JSON-completion probes to three OpenCode Zen models; it does not validate local Pydantic schemas.
- `dev_capture_items.py`: Fetches live sources for a replay corpus; the default can trigger paid video vision fallback, while `--no-video` removes that LLM path.
- `dev_ab_models.py`: Runs two LLM models over captured items for output comparison.
- `dev_check_video_score.py`: Runs `ContentAnalyzer` LLM scoring on a single video item.
- `dev_check_one_video.py`: Fetches video transcript, invoking vision LLM fallback when subtitles are absent.
- `dev_test_laguna.py` / `dev_test_laguna_ru.py`: Tests scoring or Russian enrichment prompts against Laguna model endpoints.

> **CRITICAL RULE**: Never run any section-C LLM script, `horizon`, or `daily-run.sh` without explicit owner approval. Default to offline pytest; run only the specific section-B checks whose network and side effects are acceptable.

### D. Host-Specific & Operational / Deployment Scripts
Requires specific hardware, virtual environments, or production infrastructure:

- **Host-Specific Hardware / Venv**:
  - `dev_narrate_article.py`: Mac-side narration driver. Requires Apple Silicon host, `~/tts/.venv`, TeraTTSv2, Whisper, `ffmpeg`, and upload credentials; its optional pronunciation-review path also creates the configured AI client and may bill.
  - `dev_check_asr.py`: ASR smoke test using `mlx-whisper` on Apple Silicon.
- **Operational & Deployment**:
  - `daily-run.sh`: Legacy/alternative production runner (pulls git, runs the paid pipeline, and updates `gh-pages`).
  - `dev_reindex_archive.py`: Reads archive files, sends HTTP requests to Elasticsearch, and mutates the configured index.
- **Interactive Setup**:
  - `setup_r2.py`: Interactive Cloudflare R2 bucket setup (writes credentials to `.env`).
  - `setup_telegram.py`: Interactive Telegram bot token setup (writes token to `.env`).

## 3. Dev, Setup, and Operational Boundaries

- **Development vs. Operational**: Dev scripts are for debugging and testing. Operational scripts (`daily-run.sh`, `dev_narrate_article.py`) target deployment environments or remote servers; do not invoke them in general development.
- **Setup Scripts & Secret Handling**: Setup scripts (`setup_r2.py`, `setup_telegram.py`) write credentials to `.env`. Secrets must **never** be printed to terminal output, logged, or committed to source control.

## 4. Verification Instructions

When working in or verifying `scripts/`, use safe narrow checks:

1. **Syntax Compilation (Python & Bash)**:
   ```bash
   python3 -m py_compile scripts/*.py
   bash -n scripts/daily-run.sh
   ```
2. **Whitespace & Git Diff Verification**:
   ```bash
   git diff --check -- scripts/AGENTS.md
   ```
