# AGENTS.md — Processing Layer Guide (`src/processing/`)

## Scope & Purpose

`src/processing/` owns profile loading and validation (`profiles.py`), content sampling and budget truncation (`content.py`), tool registration and search fallbacks (`tools.py`), and exports the public processing interface. Pipeline deduplication and filtering stages in `orchestrator.py` consume these components.

## Module Map

- `profiles.py`: Pydantic definitions (`ProfileDefinition`, `ProfileContent`, `ProfileEnrichment`, `ProfileBlock`), prompt file loading, and `ProfileRegistry`.
- `content.py`: Comments separation (`split_content`) and character budget sampling (`select_content`).
- `tools.py`: Search execution (`WebSearchTool`), backend fallback chain, error classification, and tool dispatch (`ToolRegistry`).
- `__init__.py`: Public export surface (`LoadedProfile`, `ProfileRegistry`).

## Key Architecture & Contracts

### 1. Selection, Deduplication & Profile Routing Contracts
- **Profile Routing**:
  - Source `profile` in `data/config.json` can be `"auto"`, a single profile ID (e.g. `"tech-news"`), or a candidate list (e.g. `["tech-news", "video"]`).
  - Single explicit profiles skip LLM classification; candidate lists restrict LLM routing to the declared subset; `"auto"` routes across all registered profiles.
  - `ProfileRegistry.validate_source_references()` rejects non-existent profile IDs, duplicate candidate entries, or candidate lists containing `"auto"`.
- **Content Selection**:
  - `split_content()` isolates article body from community comments around `--- Top Comments ---`.
  - `select_content()` caps main text to `analysis_max_chars` or `enrichment_max_chars` using sampling strategies (`"prefix"` truncation or `"head-middle-tail"` windowing).
- **Deduplication Contracts**:
  - **Cross-Source URL Dedup**: `src/orchestrator.py:_deduplication_url_key()` normalizes URLs to `(scheme, username, password, host, port, path, query)`. Items are grouped by `(*url_key, requested_profile)`. Identical URLs with distinct profile requests remain unmerged.
  - **AI Topic Dedup**: Stage 5 (`merge_topic_duplicates`) groups items by profile and presents them score-descending to one LLM call per profile. The implementation treats the first model-returned index in each group as primary, merges duplicate content into it, and records lineage in `topic_dedup_members`; it does not currently canonicalize overlapping groups or independently enforce that the chosen primary has the highest score.

### 2. Deterministic Ordering
- `ProfileRegistry.load()` sorts profile directories via `sorted(root.glob("*/profile.json"))` to ensure reproducible loading order across filesystems.
- Source candidate profile lists retain explicit declaration order.
- Deduplication processing sorts input items deterministically by importance score descending before and after topic dedup.
- Deduplication warning categories are sorted alphabetically (`sorted(set(duplicate_categories))`).

### 3. Content Budgets
- `ProfileContent` enforces bounded char budgets via Pydantic (`ge=500, le=100_000`):
  - `analysis_max_chars` (default 1000) & `enrichment_max_chars` (default 8000) for body text.
  - `analysis_comments_max_chars` (default 1500) & `enrichment_comments_max_chars` (default 2000) for community comments.
  - `classification_max_chars` (default 2000).
- `select_content()` caps the selected body and comment components at their respective profile limits; total prompt size also includes titles, contracts, and other scaffolding.

### 4. External Tool Degradation
- `WebSearchTool` queries DDGS text search with an automatic backend fallback sequence: `(None, "duckduckgo", "yahoo", "yandex")`.
- Distinguishes valid empty hits from network/service outages (`SearchOutcome.status` `"ok"` vs `"error"`).
- Classifies failures into `SearchErrorCode`: `"rate_limited"` (429), `"timeout"`, `"invalid_response"`, `"unavailable"`.
- `WebSearchTool.execute()` returns `[]` on search errors instead of raising exceptions, allowing downstream enrichment blocks to degrade gracefully.

### 5. Public Config Coupling
- `ProfileDefinition` enforces `extra="forbid"` for strict validation of `profile.json` files under `profiles/`.
- `ProfileRegistry` validates profile IDs referenced by `models.py` source configs.
- Per-profile `processing.profile_settings.<profile>.topic_dedup` in runtime config controls whether Stage 5 AI deduplication runs for that profile; there is no top-level or CLI toggle.

## Focused Offline Tests

- `tests/test_profiles.py` — Profile schema validation, directory loading, candidate list validation.
- `tests/test_content_selection.py` — `split_content` marker splitting, `"prefix"` and `"head-middle-tail"` sampling.
- `tests/test_search.py` — `WebSearchTool` backend fallbacks, error handling, hit conversion.
- `tests/test_cross_source_duplicates.py` — URL identity keys, cross-source deduplication.
- `tests/test_balanced_digest.py` — Digest filtering, topic deduplication, profile balancing.
