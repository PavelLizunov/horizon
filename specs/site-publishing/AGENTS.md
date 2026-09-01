# Site Publishing SDD Guide (`specs/site-publishing/AGENTS.md`)

This directory governs the static site portal, article page rendering, dynamic source collection listings, search indexing, and deployment shipping to public web ingress.

## 1. Document Trio Authority & Status

- **`spec.md`**: Defines site page structure (`/`, `/digest/`, `/collection/`, `/checks/`), search/feed capabilities, and public presentation standards. Its Lunr/Atom/RSS promise is stale: generated digest pages are excluded from the MkDocs index, archive search uses the separate Elasticsearch API, and legacy feed files are excluded. Reconcile that public contract explicitly before changing search or feed behavior.
- **`plan.md`**: Architecture for `DailySummarizer` article generation, `StorageManager` index updates, `mkdocs build`, and `deploy/run-daily.sh` ingress shipping.
- **`tasks.md`**: Implementation checklist. Changes must stay in sync with `src/ai/summarizer.py`, `scripts/dev_collection_status.py`, and `deploy/run-daily.sh`.
- **Hierarchy & Traceability**: `spec.md` > `plan.md` > `tasks.md`. Requirements for public page sections must trace from `spec.md` to `summarizer.py` rendering logic and offline tests.

## 2. Local Non-Negotiable Invariants

1. **Secret & Token Isolation**: No credentials, API keys, or sensitive search tokens may be emitted into public site files, HTML templates, or search indexes.
2. **Public Reader Sanitization**: Article views sanitize internal verification states and omit token/cost details. The checks page currently publishes usage despite older constitution/spec language requiring all estimates to remain private; treat that as an unresolved owner-level compatibility decision, not a cleanup edit.
3. **Semantic Accessibility**: Material for MkDocs templates must produce responsive, high-contrast, semantic HTML with mobile touch targets.
4. **Index Placeholder Management**: `docs/digest/index.md` is a tracked repository file with an empty-state placeholder for clean builds; deployment scripts (`deploy/run-daily.sh`) regenerate live listings prior to publishing.
