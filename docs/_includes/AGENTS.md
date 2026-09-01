# AGENTS.md — Includes Directory (`docs/_includes/`) Guide

This file defines rules for maintaining template partials inside `docs/_includes/`. See [`docs/AGENTS.md`](../AGENTS.md) and root [`AGENTS.md`](../../AGENTS.md) for general documentation policies.

## 1. Scope & Purpose

- `docs/_includes/` contains legacy Jekyll HTML template includes (such as `head-custom.html`).
- The entire `_includes/` directory is excluded from MkDocs builds via `exclude_docs` in `mkdocs.yml`.

## 2. Template Safety & Invariants

- **Jekyll Compatibility**: Maintain Liquid tag syntax (e.g., `{{ '/assets/css/horizon.css' | relative_url }}`) without breaking resolution against legacy assets in `docs/assets/css/` or `docs/assets/js/`.
- **Path Validation**: Verify that any CSS, JS, or icon assets referenced in HTML partials actually exist (e.g., `docs/assets/css/horizon.css`, `docs/assets/js/horizon.js`).
- **No Secret/Script Leakage**: Do not inject unverified inline scripts, external CDNs, or credentials into HTML head headers.
