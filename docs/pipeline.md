---
layout: default
title: Pipeline Map
---

# Pipeline Map

`src/orchestrator.py` is the largest file in the project (~950 lines) and wires
every stage together. This page is the map: what runs in what order, which
method owns it, and which config keys steer it. Read this before opening the
file — it is a long file, not a complicated one.

> **Why it is not split into stage modules.** Upstream
> ([Thysrael/Horizon](https://github.com/Thysrael/Horizon)) edits
> `orchestrator.py` on most feature releases, and this fork stays merge-friendly
> on purpose (see `AGENTS.md` §9). Splitting the single most-edited upstream
> file into `stages/*.py` would turn every future merge into a conflict, in
> exchange for readability that this document provides for free. If the fork
> ever stops tracking upstream, revisit that trade.

## The Run

`HorizonOrchestrator.run()` is the whole story, numbered 1–7 in the source.

| # | Stage | Method | Config |
|---|-------|--------|--------|
| 0 | Email subscription check | `EmailManager.check_subscriptions` | `email.imap_enabled` |
| 1 | Time window | `_determine_time_window()` | `collection.time_window_hours`, `--hours` |
| 2 | Fetch every enabled source, concurrently | `fetch_all_sources()` | `sources.*` |
| 3 | Merge same-URL items across sources | `merge_cross_source_duplicates()` | — |
| 4 | Score with the LLM (1st pass) | `analyze_items()` | `ai.*`, profile `analysis.md` |
| 5 | Filter, dedup by topic, balance | `select_digest_items()` | `processing.profile_settings`, `digest.*` |
| 6 | Enrich with web search (2nd pass) | `enrich_items()` | profile `enrichment.md` |
| 7 | Render + deliver per language | `_generate_summary()`, `DailySummarizer` | `ai.languages`, `digest.profile_order` |

Stage 5 expands into `filter_items()` → `merge_topic_duplicates()` →
`apply_balanced_digest()` → `passes_profile_filter()`. Stage 2 fans out through
`_fetch_with_progress()`, which catches per-source exceptions so one dead source
cannot end the run.

## Reporting Types

Defined at the top of `orchestrator.py`, before the class:

- `SourceFetchOutcome` — one source's result: `success` / `empty` / `failure`.
- `FetchReport` — all outcomes; `.status`, `.all_failed`, `.failure_message()`.
  `run()` aborts only when **every** source failed.
- `FilteringPipelineResult`, `BalancedDigestResult` — stage-5 diagnostics.
- `_deduplication_url_key()` — URL normalisation shared by the dedup stages.

These are also what the MCP server surfaces, so treat their shapes as public.

## Adding a Source

Five files, in this order (`AGENTS.md` §4 has the same list):

1. `src/models.py` — config model + `SOURCE_REGISTRY` entry.
2. `src/scrapers/<name>.py` — subclass `BaseScraper`, implement `fetch(since)`.
3. `src/orchestrator.py` — a wiring block in `fetch_all_sources()`.
4. `data/config.example.json` — a documented section.
5. `tests/` — offline coverage with the network mocked.

The registry parity test (`tests/test_mcp_adapter.py`) fails if you skip step 1,
and its fixture needs the new source too.

## What This Fork Changed

Everything above is upstream. This fork adds:

| Area | Files |
|------|-------|
| YouTube video source | `src/scrapers/video.py`, `src/services/video_cli.py`, `profiles/video/`, `tests/test_video.py` |
| Config for it | `VideoConfig` / `VideoChannelConfig` in `src/models.py` |
| Wiring | ~6 lines in `fetch_all_sources()` |
| Deployment | `deploy/` |

`src/orchestrator.py` is otherwise untouched, which is what keeps upstream
merges cheap. Keep it that way: put video logic in `video.py`, not here.

See `docs/video-source.md` for the video module itself.
