# AGENTS.md — CSS Assets (`docs/assets/css/`) Guide

This directory contains CSS assets. Parent rules live in [`docs/assets/AGENTS.md`](../AGENTS.md) and [`docs/AGENTS.md`](../../AGENTS.md).

## Asset Classification

- **`docs/assets/css/horizon.css`**: Legacy upstream stylesheet. Excluded from the public digest build (`exclude_docs` in `mkdocs.yml`) to preserve merge compatibility with upstream Thysrael/Horizon. **Do not modify.**
- **`docs/assets/horizon-digest.css`**: Active custom stylesheet for `https://digest.ninitux.com/` (`extra_css` in `mkdocs.yml`). All active site style changes belong in `horizon-digest.css`.

## Active CSS Invariants (`horizon-digest.css`)

- **System Font Stack**: Uses `--hz-font-text` and `--hz-font-meta` system fonts without `@import` or external CDN font dependencies.
- **Dual Scheme Independence**: Theme variables are defined independently for light (`default`) and dark (`slate`) color schemes.
- **Reduced Motion**: Preserves `@media (prefers-reduced-motion: reduce)` rules (e.g. disabling sticky player transitions).
- **Asset Integrity**: Do not edit `css/horizon.css` or modify binary assets.
