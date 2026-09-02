# AGENTS.md — Documentation Directory (`docs/`) Guide

This file defines rules and boundaries for working inside `docs/`. Global project rules and architecture live in the root [`AGENTS.md`](../AGENTS.md).

## 1. Public Site vs. Repository-Only Manual

The `docs/` tree serves two distinct purposes governed by `mkdocs.yml`:

- **Public Digest Site** (built with MkDocs Material for `https://digest.ninitux.com/`):
  - Tracked entrypoints: `docs/index.md`, `docs/digest/index.md`, `docs/collection.md`, `docs/checks.md`, `docs/search.md`, and `docs/not-found.md`.
  - Static site assets live in `docs/assets/`.
- **Repository-Only Manual** (excluded from the public MkDocs build via `exclude_docs` in `mkdocs.yml`):
  - Internal architecture and operational guides (`pipeline.md`, `configuration.md`, `scrapers.md`, `video-source.md`, `narration.md`, `profiles.md`, `scoring.md`, `extractors.md`, `telegram-delivery.md`, `twitter-cookies.md`, `vpn-radar.md`, and `verification/`).
  - Retained for GitHub reading without cluttering public digest readers.
  - Legacy upstream Jekyll files (`_config.yml`, `_includes/`, `_posts/`, `feed-*.xml`, `assets/css/horizon.css`, `assets/js/horizon.js`) are also in `exclude_docs` to preserve upstream merge compatibility.
  - Repository guidance files (`AGENTS.md` and `**/AGENTS.md`) are excluded explicitly; they are agent instructions, not public site content.

## 2. Generated vs. Live Documentation Boundaries

- `docs/digest/index.md`: GENERATED page tracked with an empty-state placeholder so fresh clones can build. `deploy/run-daily.sh` regenerates the listing before every build. Do not overwrite the placeholder format manually in source control.
- `docs/digest/*`: Individual generated issue pages produced at runtime are excluded from navigation and gitignored; `docs/digest/AGENTS.md` is an explicit tracked exception.
- `index.md`, `search.md`, and `not-found.md` are manually maintained public pages. `collection.md` and `checks.md` are tracked empty-state/placeholders regenerated from runtime config or verification state by their `scripts/dev_*_status.py` owners; change their templates/generators rather than committing live data.

## 3. Link, Path, and Structure Safety

- **Link Validation**: All relative Markdown links must resolve to existing files within `docs/` or the root repository.
- **Anchor and Slug Handling**: Generated aggregate digests retain raw `<a id="item-...">` anchors, so `mkdocs.yml` sets `validation.anchors: ignore`. Telegram links to the per-article `{slug}/` page, where `slug` is the same stable anchor ID without `item-`; do not alter that derivation without updating renderer, delivery tests, and publishing docs together.
- **Nav Sync**: When adding or renaming public site pages, update the `nav` section in `mkdocs.yml` and verify `exclude_docs` / `not_in_nav` rules.

## 4. Measurement & Content Rules

- Do not invent performance figures or token counts in docs; reference verified benchmarks or root guidelines.
- Do not alter existing markdown documentation outside explicit task scope.
