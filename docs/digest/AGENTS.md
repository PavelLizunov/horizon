# AGENTS.md — Digest Content & Publishing Directory (`docs/digest/`) Guide

This file defines local rules for working inside `docs/digest/`. Parent guidelines live in [`docs/AGENTS.md`](../AGENTS.md) and the root [`AGENTS.md`](../../AGENTS.md).

## 1. Directory Boundaries & File Roles

- **`docs/digest/*` (Runtime Generated Issue Pages)**:
  - Issue directories (`YYYY-MM-DD-lang/`) and individual article pages (`*.md`) are written at runtime by `StorageManager.publish_site_pages()` (`src/storage/manager.py`).
  - Generated pages are gitignored and excluded from navigation (`not_in_nav: digest/*`); `.gitignore` explicitly keeps this `AGENTS.md` tracked, while `mkdocs.yml` excludes all agent guides from the site.
  - **Do not manually edit** generated article pages.

## 2. Invariants & Deep-Link Contracts

- **Deep-Link Anchor Contracts**:
  - Raw HTML anchors (`<a id="item-..."></a>`) inside article headers are contractually tied to Telegram notification deep links.
  - `mkdocs.yml` sets `validation.anchors: ignore` specifically to allow these raw HTML anchors without breaking site builds. Never alter or remove anchor target formats in generated markdown.
- **Navigation Isolation**:
  - Generated issue pages are excluded from MkDocs nav to prevent build warnings (`not_in_nav`).
  - The archive index is the site's primary issue listing; individual article pages are also reached through Telegram deep links and archive-search results.

## 3. Key Generators & Code Paths

- **Storage & Indexing**: `src/storage/manager.py` (`StorageManager.publish_site_pages`, `StorageManager.write_site_index`)
- **Pipeline Deployment Runner**: `deploy/run-daily.sh`
- **Site Configuration**: `mkdocs.yml`
