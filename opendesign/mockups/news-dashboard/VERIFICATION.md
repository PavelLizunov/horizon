# Prototype verification

## Observed on 30 September 2026

Local Chromium headless (installed build 1228), through the Tailnet-bound artifact
server. Browser automation used temporary Playwright tooling outside this repo.

22 interaction/resource checks passed:

- Five hero tiles and nine additional archive cards.
- Bookmark creation and saved-only view, persisted across reload.
- Article dialog open/Escape dismissal, with focus restored to its opener.
- Recently opened history.
- Descending score sort across all 14 stories.
- Topic and period filters, text search, empty results and reset.
- Light/dark theme, persisted across reload.
- Loading state and recovery, simulated error and retry.
- No document or dialog horizontal overflow at 390px and 320px widths.
- No uncaught page errors or failed local asset requests.

The OpenDesign root viewer loads the manifest and opens the prototype via keyboard
Enter. Focus restoration was checked separately. Targeted axe-core checks returned
no violations for `color-contrast`, `button-name`, `label`, `image-alt`,
`aria-valid-attr-value`, and `aria-dialog-name` in light/dark themes. This is not a
complete accessibility audit or a physical-device touch test.

The unchanged Python repository suite passed: **862 passed**. `node --check` on
the compiled app and `git diff --check` also passed.

## Limits

The configured remote browser could not reach the Tailnet preview (navigation
timeout); interaction verification therefore ran on the preview host itself.
Reachability from the user's device has not been proven. The preview serves only
OpenDesign artifacts, not the repository root, and makes no production API calls.
No production deployment, actual archive feed, real audio, image-generation model,
or cross-device synchronization is included.

## Visual/prose review

One editorial direction: local IBM Plex fonts, five hand-authored SVG cover
families, a dominant lead tile, and a narrow recent-reading sidebar. Screenshots
were inspected at desktop and mobile widths. No placeholder controls or fake
successful audio actions. Demo status and score semantics remain explicit.
Dark-mode penguin visibility was corrected; bookmark touch targets extend to
44px without increasing the metadata row's visual weight.
