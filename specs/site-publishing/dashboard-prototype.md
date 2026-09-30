# News dashboard prototype

## Outcome and authorization

The user approved a clickable mockup first, not production integration. Build a
Russian editorial homepage with one lead tile and four smaller stories, followed
by an archive-spanning feed. Preserve the product name and existing penguin.
Use a one-off editorial direction rather than creating a reusable design system.

## Scope and invariants

- Files: `opendesign/mockups/news-dashboard/`, OpenDesign viewer/manifest, and this
  task record. Do not change production homepage, publishing, search API, or models.
- React local state: search, topic and period filters, newest/score sorting,
  saved stories, recently opened stories, article dialog and theme toggle.
- Namespaced localStorage retains bookmarks/history/filter/theme choices.
- Clearly label realistic sample news and scores as demonstration data, not an
  actual fetched publication. Covers are hand-authored inline SVG illustrations,
  not model-generated images or evidence. External model generation is deferred.
- Demonstrate loading, empty and recoverable error states. No false audio play:
  audio availability is sample metadata; no real track is bundled.
- No image model deployment or quant selection. Future production integration
  and asynchronous local cover generation remain separate next steps, not waived.

## Design read

Editorial news homepage for a personal Russian-language reading archive.
ENERGY 3 / RHYTHM 3 / MOTION 2. Newspaper-like neutral paper, ink text, blue
interaction accent, illustrated tile imagery. A dominant story and varied tile
sizes establish priority. Serif headlines distinguish reading from machine
metadata; small sans-serif labels clarify scores/dates. Short feedback transitions
explain bookmark state changes. Mobile becomes a vertical feed with 44px touch controls.
Both light and dark themes, visible keyboard focus, no CDN runtime requests.

## Verification

Exercise every control in the browser, persistence, article dismissal/focus,
search reset, empty and error/retry states. Check five hero tiles, sort ordering,
phone/desktop overflow, missing assets, console errors and text contrast.
Serve only inspected OpenDesign artifacts on the verified Tailnet address,
port 8289, with a tracked managed server job. Commit/push a dedicated task branch.
Do not claim production performance or user-side reachability from local checks.

## Status

- [x] Inspected current homepage, archive search/schema, and site styling.
- [x] Confirmed prototype-first scope and one-off editorial direction.
- [x] Build and browser verification: 22 interaction/resource checks, local
  Chromium; light/dark targeted accessibility checks, viewer keyboard navigation,
  dialog focus restoration. Full Python suite: 862 passed.
- [x] Preview server: managed job `bash-106`, bound only to the verified Tailnet
  address/port. Root viewer and direct prototype return the expected artifacts.
- [x] Commit and push the dedicated task branch: implementation `7083837`,
  backed up to `origin/design/news-dashboard-prototype`.

Evidence and limitations: `opendesign/mockups/news-dashboard/VERIFICATION.md`.
The remote browser navigation timed out; client-side network reachability remains
unverified. Browser verification ran locally on the host. No production changes.
Prototype image covers are inline SVG, not a deployed image-generation model.
The prototype branch descends from the verified narration fix branch, preserving
that previous work; only OpenDesign files and this record belong to this task.

Unknowns: local image-generation GPU/VRAM and deployment host, final feed contract,
production personalization and multi-device bookmark storage. These do not block
the isolated prototype.
