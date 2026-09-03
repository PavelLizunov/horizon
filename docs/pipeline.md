---
layout: default
title: Pipeline Map
---

# Pipeline Map

`src/orchestrator.py` is the largest file in the project and wires every stage
together. This page is the map: what runs in what order, which method owns it,
and which config keys steer it. Read this before changing pipeline behavior.

> **Why it is not split into stage modules.** Upstream
> ([Thysrael/Horizon](https://github.com/Thysrael/Horizon)) edits
> `orchestrator.py` on most feature releases, and this fork stays merge-friendly
> on purpose (see `AGENTS.md` §9). Splitting the single most-edited upstream
> file into `stages/*.py` would turn every future merge into a conflict, in
> exchange for readability that this document provides for free. If the fork
> ever stops tracking upstream, revisit that trade.

## The Run

`HorizonOrchestrator.run()` owns the numbered 1–7 flow; verification is an
optional shadow stage between enrichment and rendering.

| # | Stage | Method / owner | Config |
|---|-------|----------------|--------|
| 0 | Email subscription check | `EmailManager.check_subscriptions` | `email.imap_enabled` |
| 1 | Time window | `_determine_time_window()` | `collection.time_window_hours`, `--hours` |
| 2 | Fetch every enabled source concurrently | `fetch_all_sources()` | `sources.*` |
| 3 | Merge items with the same normalized URL and requested profile | `merge_cross_source_duplicates()` | — |
| 4 | Classify and score with the LLM | `analyze_items()` | `ai.*`, profile `match.md` / `analysis.md` |
| 5 | Threshold, topic-deduplicate, expand selected discussion, and balance | `select_digest_items()` | `processing.profile_settings`, `digest.*` |
| 6 | Enrich with allowed tools and a second LLM pass | `enrich_items()` | profile `enrichment.md` |
| V | Capture selected lineage, extract/verify claims, update incidents | `src/verification/`, `ShadowLedger` | `verification.*` |
| 7 | Render pages/summaries, index search, and deliver email/webhooks per language | `DailySummarizer`, `SearchIndexer` | `ai.languages`, `digest.*`, `search.*`, delivery config |

Stage 5 first applies `passes_profile_filter()`, then optional
`merge_topic_duplicates()` and `apply_balanced_digest()`. Twitter discussion
expansion can trigger targeted re-analysis, so eligibility and balancing are
applied again afterward. Scrapers return a healthy empty result only when an
attempt succeeded (or no endpoint was configured); multi-endpoint scrapers raise
only if every attempted endpoint failed. Stage 2 fans out through
`_fetch_with_progress()`, which records those per-source failures so one dead
source cannot end the run.

## Reporting Types

Defined at the top of `orchestrator.py`, before the class:

- `SourceFetchOutcome` — one source's result: `success` / `empty` / `failure`.
- `FetchReport` — all outcomes; `.status`, `.all_failed`, `.failure_message()`.
  `run()` aborts only when **every** source failed.
- `FilteringPipelineResult`, `BalancedDigestResult` — stage-5 diagnostics.
- `_deduplication_url_key()` — URL identity normalization used by stage 3.

These dataclasses are internal pipeline diagnostics. The MCP service selects and
serializes parts of them into its own documented response envelopes; treat the MCP
envelopes and artifact files—not the Python dataclasses themselves—as the public contract.

## Adding a Source

Five files, in this order (`AGENTS.md` §4 has the same list):

1. `src/models.py` — config model + `SOURCE_REGISTRY` entry.
2. `src/scrapers/<name>.py` — subclass `BaseScraper`, implement `fetch(since)`.
3. `src/orchestrator.py` — a wiring block in `fetch_all_sources()`.
4. `data/config.example.json` — a documented section.
5. `tests/` — offline coverage with the network mocked.

The registry parity test (`tests/test_mcp_adapter.py`) fails if you skip step 1,
and its fixture needs the new source too.

## Major Fork Extensions

| Area | Primary owners |
|------|----------------|
| YouTube video source and sidecar | `src/scrapers/video.py`, `src/services/video_cli.py`, `profiles/video/` |
| 4PDA, GDELT, Google News, OSS Insight, and OpenBB sources | `src/scrapers/`, `src/models.py` |
| Profile routing, topic deduplication, and balanced selection | `src/processing/`, `src/orchestrator.py` |
| Evidence Ledger verification and incident history | `src/verification/`, verification sections in `src/orchestrator.py` |
| Static article pages, archive search, narration, and host publishing | `src/ai/summarizer.py`, `src/services/search.py`, `scripts/`, `deploy/` |
| Staged MCP tools/resources and run artifacts | `src/mcp/` |

Keep source-specific extraction inside its scraper and preserve the orchestrator as
integration wiring. See [Video Source](video-source.md) and
[Verification](verification/) for the two largest specialized flows.
