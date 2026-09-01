# Processing Profiles Engine — Guide for AI Agents

This directory contains the processing profile system for Horizon. Each profile defines how content items of a specific topic or format are matched, scored, and enriched by LLM stages in the pipeline.

## 1. Directory Structure & Required Files

Every tracked profile lives in its own subdirectory under `profiles/` (e.g. `profiles/tech-news/`) and contains four runtime files plus its local `AGENTS.md` guide:

| File | Purpose |
|------|---------|
| `profile.json` | Profile metadata, character limits, sampling strategy, and enrichment block schema (`ProfileDefinition`). |
| `match.md` | Prompt used during classification/routing to evaluate if an item matches this profile. |
| `analysis.md` | Scoring rubric (0–10) and guidance used by the LLM analyzer to rate item importance. |
| `enrichment.md` | Structured synthesis prompt defining role, block instructions, and writing rules. |

Prompt filenames in `profile.json` (`match`, `analysis`, `enrichment.prompt`) must be relative paths located within the profile's directory. Prompt paths escaping the directory (e.g. `../`) are rejected by `ProfileRegistry.load()`.

## 2. Profile Contracts & Pydantic Validation

Profile JSON configurations are strictly validated by Pydantic models in `src/processing/profiles.py`:

- **`ProfileDefinition`** (`extra="forbid"`):
  - `id`: Lowercase identifier matching `^[a-z][a-z0-9_-]*$`.
  - `name`: Display name string.
  - `display_names`: Map of localized display names (e.g. `{"ru": "...", "zh": "..."}`).
  - `match`, `analysis`: Relative file paths to markdown prompts.
  - `content`: `ProfileContent` model configuring sampling and text truncation limits.
  - `enrichment`: `ProfileEnrichment` model defining prompt path and block schema.

- **`ProfileContent`** (`extra="forbid"`):
  - `analysis_max_chars`: Default 1000 (range 500–100,000). Max input text for analysis stage.
  - `enrichment_max_chars`: Default 8000 (range 500–100,000). Max input text for enrichment stage.
  - `classification_max_chars`, `analysis_comments_max_chars`, `enrichment_comments_max_chars`.
  - `sampling`: Strategy for text truncation — `"prefix"` (default) or `"head-middle-tail"` (for long posts/videos).

- **`ProfileBlock` & `ProfileEnrichment` Structural Invariants**:
  - Block `id` must be unique within the profile (`^[a-z][a-z0-9_-]*$`).
  - At most one block per profile may be marked `primary: true`.
  - The `primary` block must not be marked `optional: true`.
  - `ProfileBlock.tools` is schema-typed as `list[str]`, but the current runtime registry supports only `web_search`; tracked profiles therefore use `tools: ["web_search"]` or `tools: []`.
  - **Evidence Ledger Invariant**: Fact-checking and evidence status blocks (`fact_check`, `evidence_status`) belong exclusively to `src/verification/` and MUST NOT be declared as profile enrichment blocks.

## 3. Thresholds & Configuration Ownership

Profile directories define **anatomy and prompts only**. They do not own runtime filtering or thresholds:

- **Forbidden in `profile.json`**: Fields like `filter` or `threshold` inside `profile.json` raise a Pydantic `ValidationError` (`extra="forbid"`).
- **Owned by Runtime Config**: Thresholds and deduplication rules are configured in `data/config.json` under `processing.profile_settings` (`ProcessingConfig` / `ProfileSettingsConfig` in `src/models.py`):
  - `threshold`: Score (0.0–10.0) below which items are filtered out before enrichment.
  - `category_thresholds`: Per-category score overrides (e.g. `{"llm": 4.5, "sdd": 4.5}`).
  - `topic_dedup`: Boolean enabling topic-level deduplication (default `True`).
- **Fail-Open Behavior**: If a profile has no entry in `processing.profile_settings`, the orchestrator fails open, admitting all items regardless of score while logging a warning.

## 4. Built-in Packaging & Fallback Mechanism

`ProfileRegistry.load(profiles_dir, default_profile, base_dir)` handles discovery:
- If `profiles_dir` is `"profiles"` and does not exist in the working directory, `ProfileRegistry` falls back to packaged `BUILTIN_PROFILES_DIR` (`src/_builtin_profiles`) when that directory exists.
- Validates that `default_profile` exists in the loaded profile set (the runtime config default is `"tech-news"`) and rejects duplicate profile IDs.
- Source-reference validation is a separate `ProfileRegistry.validate_source_references()` call; it rejects unknown IDs, duplicates, and `"auto"` inside explicit candidate lists.

## 5. Verification & Tests

To verify profile integrity offline without API keys or network calls:

```bash
.venv/bin/pytest tests/test_profiles.py -q
```

This suite validates profile loading, schema enforcement, path boundaries, block constraints, and runtime config integration.
