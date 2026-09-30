# AGENTS.md — Static Assets (`docs/assets/`) Guide

This directory holds static assets for the MkDocs Material public digest site (`https://digest.ninitux.com/`). Parent rules live in [`docs/AGENTS.md`](../AGENTS.md) and the root [`AGENTS.md`](../../AGENTS.md).

## Active vs. Legacy/Excluded Assets

- **Active Assets** (referenced in `mkdocs.yml`):
  - `horizon-digest.css`: Custom digest stylesheet (`extra_css`).
  - `horizon-player.js`: Custom narration player controller (`extra_javascript`).
  - `horizon-search-redirect.js`: Header search redirect script (`extra_javascript`).
  - `horizon-dashboard.css` / `horizon-dashboard.js`: Scoped news homepage and real-article saved/history enhancement; Material owns palette and instant navigation. Storage namespace is `hz-dashboard-v1`, not prototype storage. Catalog failures retain static links.
  - `dashboard/`: Local licensed fonts and trusted decorative SVG cover families. Catalog JSON exists only in build output, never tracked live data. SVG variations are deterministic; no untrusted markup or model calls.
  - `hz-penguin.png`: Site mascot logo and favicon (`theme.logo`, `theme.favicon`).
- **Legacy / Excluded Assets**:
  - `css/horizon.css`: Upstream legacy stylesheet (excluded via `exclude_docs` in `mkdocs.yml`).
  - `js/horizon.js`: Upstream legacy script (excluded via `exclude_docs` in `mkdocs.yml`).
  - Legacy documentation and upstream images (`email.png`, `feishu_*.png`, `horizon-header.svg`, `hz-head.png`, `hz-mark.png`, `one_news_*.png`, `overview_*.png`, `terminal_log.png`).

## Asset Management & Binary Safety

- **No Asset Re-encoding**: Do not re-encode, compress, or modify binary assets (`.png`, `.svg`) to prevent unnecessary binary diffs and git repository bloat.
- **Do Not Modify Excluded Assets**: Retain files in `css/` and `js/` untouched to maintain merge compatibility with upstream Thysrael/Horizon.
- **Active Asset Scope**: Edits for active site styling or scripts must target top-level `docs/assets/` files (`horizon-digest.css`, `horizon-player.js`, `horizon-search-redirect.js`, `horizon-dashboard.css`, `horizon-dashboard.js`).

## Architecture & UX Constraints

- **Accessibility & Reduced Motion**: Active CSS/JS must preserve full keyboard accessibility, semantic `aria-*` contracts, accessible color contrast, and `@media (prefers-reduced-motion: reduce)` behavior.
- **Fallback Behavior**: Pages must remain functional without JavaScript. Custom JS enhancements must degrade gracefully to standard HTML controls.
- **Verification**: Any browser- or runtime-sensitive changes require focused checks and static validation (`git diff --check`).
