---
layout: default
title: Evidence Ledger preflight
---

# Evidence Ledger preflight

Repository state inspected on 2026-08-11 before the first verification change.

## Baseline

- Repository revision: `b3c327534fb04491dda6035a0751a6abb43d9dec`.
- The existing untracked `.test-tmp/` directory predates this work and is out of
  scope.
- Python is 3.11+; configuration uses Pydantic v2 models in `src/models.py`.
- The offline test command is `pytest`; GitHub Actions runs it on Python 3.12.
- A real `horizon` run is paid and must not be used as a smoke test without the
  owner's approval.

## Actual pipeline

`src/main.py` owns CLI/bootstrap concerns and calls `HorizonOrchestrator.run()`;
it contains no pipeline stages. All verification wiring belongs in
`src/orchestrator.py`, whose relevant flow is:

```text
fetch_all_sources()
  -> merge_cross_source_duplicates()
  -> analyze_items()
  -> select_digest_items()
       -> filter_items(apply_balance=False)
            -> optional per-profile merge_topic_duplicates()
       -> _expand_twitter_discussion()
       -> reapply profile filters
       -> apply_balanced_digest()
  -> enrich_items()
  -> DailySummarizer rendering and delivery
```

`DailySummarizer` is a pure renderer. Generated prose is created by
`ContentEnricher` and stored as `ContentArtifact` / `ContentBlock` records on a
`ContentItem`. A publication audit must therefore inspect enriched artifacts
before `DailySummarizer`, not introduce a second summary generator.

## Existing contracts

| Concern | Current contract |
|---|---|
| Normalized item | `src.models.ContentItem` |
| Fetch result | `list[ContentItem]`; diagnostics in `FetchReport` |
| URL dedup | `HorizonOrchestrator.merge_cross_source_duplicates()` |
| Topic dedup | `HorizonOrchestrator.merge_topic_duplicates()` |
| Final selection | `HorizonOrchestrator.select_digest_items()` |
| Profiles | `ProfileRegistry.load()` and `ProfileSettingsConfig` |
| AI abstraction | `AIClient` / `create_ai_client()` |
| Web discovery | `WebSearchTool` in `src/processing/tools.py` |
| Enriched output | `ContentArtifact`, `ContentBlock`, `ArtifactSource` |
| Rendering | `DailySummarizer` |
| Atomic files | `_atomic_write_text()` and `safe_output_path()` |
| URL safety | `validate_public_http_url()` / `safe_request()` |
| MCP stages | decorators in `src/mcp/server.py`, implementation in `src/mcp/service.py` |
| Narration input | `narration_text()` in `src/ai/narration.py` |

## Constraints discovered

1. Capturing after `fetch_all_sources()` can preserve the exact normalized
   `ContentItem`, but not a source-native raw response. Scrapers may already
   extract, omit, or truncate content; video content is capped by
   `transcript_max_chars`.
2. Both URL dedup and model-assisted topic dedup can discard members and append
   their content to the surviving item. Their optional sidecar maps now retain
   those members. The selected-input snapshot is captured after Twitter
   discussion expansion, score re-filtering and balancing, rather than inferred
   from `metadata["merged_sources"]`.
3. `WebSearchTool.search()` now distinguishes a healthy empty result from a
   typed backend error. The existing `execute()` list shape remains stable for
   enrichment. Snippets are discovery records, never evidence.
4. `fetch_public_document()` shares the repository's public-URL resolver, pins
   the validated address for the connection, revalidates every redirect and
   adds streaming byte, wall-clock and MIME limits. Existing `safe_request()`
   consumers are unchanged.
5. Token accounting is per provider, not per stage. The first version may count
   verification calls and wall time, but must not claim stage token attribution.
6. Narration object names hash audio bytes. There is no narration text hash or
   automatic invalidation contract today; that work is outside text-verification
   v1.
7. The static MkDocs site intentionally publishes the digest only. These design
   documents remain repository documentation and are excluded from the site.

## Integration decision

The shadow MVP adds one optional verification stage in
`HorizonOrchestrator.run()` after enrichment and before rendering. It consumes
the selected items, fetched and post-selection input snapshots, dedup
membership, and final `ContentArtifact` objects under a five-call-per-item
default ceiling. With verification disabled, existing output is unchanged;
shadow auditing does not mutate artifacts or citations.
