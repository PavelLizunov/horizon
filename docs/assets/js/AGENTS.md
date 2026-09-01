# AGENTS.md — JavaScript Assets (`docs/assets/js/`) Guide

This directory contains JavaScript assets. Parent rules live in [`docs/assets/AGENTS.md`](../AGENTS.md) and [`docs/AGENTS.md`](../../AGENTS.md).

## Asset Classification

- **`docs/assets/js/horizon.js`**: Legacy upstream script. Excluded from public site builds (`exclude_docs` in `mkdocs.yml`) to preserve upstream merge compatibility. **Do not modify.**
- **`docs/assets/horizon-player.js` & `docs/assets/horizon-search-redirect.js`**: Active scripts loaded by MkDocs (`extra_javascript` in `mkdocs.yml`). All active JS logic belongs in top-level `docs/assets/` files.

## Active JS Invariants

- **One-Player Architecture**: A single `PlayerController` instance in `horizon-player.js` manages both inline and sticky UI views for the `<audio class="hz-narration">` element, preventing duplicate playback or audio resets during scroll or instant nav page swaps (`document$.subscribe`).
- **Progressive Enhancement & Fallback**: The HTML ships native `<audio controls>`. JS mounts custom views and removes `controls` only after successful initialization (`data-hz-enhanced="1"`). Any exception in `mount()` invokes `destroy()` to safely restore native controls.
- **Accessibility & Navigation**: Keyboard shortcuts (`Space`/`k`, `j`/`l`, arrows, `m`, `,`/`.`), `aria-live` status announcements, and a `popover` speed menu with Escape plus Arrow/Home/End focus movement.
- **Verification**: Any change to active JS requires focused browser or DOM runtime verification plus static checks (`git diff --check`).
