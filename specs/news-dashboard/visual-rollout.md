# Cover/icon correction and production rollout

## Authorization and scope

The user reported a broken chip cover, explicitly requested anti-slop treatment of
icons, and authorized publishing to the existing production site after checks.
Apply the skill during these bounded corrective edits, not a passive audit with
unapproved repairs. Preserve the approved editorial design, URLs, catalog/schema,
quality gates, existing user changes, and services. No DSH restart or paid run.

## Intended correction and evidence

- Chip traces currently terminate at mismatched points behind/below the package;
  pin strokes use independent vertical coordinates rather than following both
  projected package faces. Trace ends/pins must meet the package coherently.
- Server stack is painted top-to-bottom, so lower blocks occlude upper fronts;
  verify draw order and correct only if visually reproduced.
- Replace font-dependent dashboard search/save/close/history glyphs with a small
  purpose-specific set of trusted SVG icons. No sparkle/robot/lightning decoration;
  the owner-approved penguin remains. Keep labels/44px targets/keyboard behavior.
- Cover grids express technical diagrams and unify topic families; they are a
  deliberate approved motif, not page-wide decorative graph paper.

## Verification and release

Render all eight families at card/lead proportions and all four seed variants,
inspect representative contact sheets, add geometry/layering/icon regressions,
repeat browser interactions/contrast and full offline suite. Commit/push exact
verified task SHA. Inspect production via trusted management path, build against
its full published archive under the shared execution lock, retain previous site
artifact and checkout SHA, publish without fetch/model/narration or overlapping
publisher, verify public site/assets/catalog/old routes. Do not push main directly.

Unknowns: deployment checkout divergence, active timers/jobs, full archive formats,
remote MkDocs version, and available pinned ingress publisher access. Resolve these
before mutating production; failed access is not permission to bypass host keys.

## Progress

- [x] Correct and verify visual assets/icons: chip traces meet projected pins;
  server blocks paint back-to-front. Search/bookmark/close icons use trusted inline
  SVG paths (no font glyphs or external-use rewriting conflicts). Video covers
  retain right-facing play direction. Eight families × four seed variants inspected.
  34 browser acceptance checks pass; 894 offline tests pass.

### Anti-slop Delivery Gate (UI)

- Hard Gate: PASS for dashboard controls/labels, real card data, empty/loading/error
  behavior, light/dark contrast (targeted axe checks), and mobile overflow. Existing
  shared Material/player icons are unchanged and were not all exercised in this
  visual fix; those controls remain covered by prior scoped checks, not a new full
  accessibility audit.
- Purpose Gate: PASS. Search magnifier locates material; bookmark stores it; close
  removes a query/history record. Removed misleading external-arrow on internal
  recent links. Approved grid backgrounds describe technical diagrams; no new
  sparkle/robot/lightning glyphs or ornamental badges.
- Liveliness: PASS. Approved editorial ENERGY 3 / RHYTHM 3 / MOTION 2 retained,
  only illustration joins/draw order and functional glyph consistency changed.
- Interactive verification: PASS for dashboard's 34 existing browser checks,
  including SVG button clicks, theme contrast, direct history, retry and storage
  failures; NOT VERIFIED for physical touch/audio playback and all existing global
  navigation/player controls in this round.

### Anti-slop Delivery Gate (Prose)

- Hard Gate: PASS; only observed counts/test results reported, no invented metrics.
- Prose/grounding: PASS; correction described by geometry, layers and icon functions.

- [x] Push exact candidates and preserve rollout/rollback metadata: visual fix
  `94a204a`, final published correction `d63b93f`. Dedicated deployment branch;
  no push to main. Previous checkout SHA and byte-identical tracked user diff
  retained in private operator rollout record. Pre-release site tar validated.
- [x] Full production archive build and initial publication: 548 articles, 408
  attached audio tracks, no missing targets. Existing tracked local changes remained
  byte-identical after checkout switch; timers unchanged and no paid run/restart.
- [x] Resolve live instant-navigation history: Material stripped inline JSON script
  snapshots on live article transitions. Escaped hidden data attributes now preserve
  snapshots; regression and actual instant/direct article history checks pass.
- [x] Public route/hash/interaction checks: 14 live browser checks passed on the
  production HTTPS origin, including five tiles, 24-card feed, SVG bookmarks,
  real article/direct history, local search, archive/collection/checks/search/API
  responses, mobile overflow, dark contrast/icon labels and no JS errors. Homepage,
  chip, catalog and final client hashes match candidate files. Catalog has 548
  articles, 408 audio flags, 467,175 bytes and `Cache-Control: no-cache`.

## Rollback and runtime evidence

The private operator record holds the previous checkout SHA, user patch/status,
pre- and final-build outputs and deployed SHA. The ingress pre-release tar outside
web root was validated by a complete listing. Rollback restores that tar through
management access and switches the production checkout to its recorded prior SHA
without discarding user changes, under the shared production lock. Rollback was
not executed on the healthy live site. Both timers remain enabled with unchanged
next runs; both one-shot services remained inactive during application. No LLM/TTS
job or service restart occurred. Catalog generation on the full archive measured
0.406 s and native build 3.96 s during the recorded preparation build. These are observed build times, not
client rendering guarantees.

Client browser verification ran on the public origin from local Chromium. This
proves the tested path, not every physical device or all original archive anchor
links; 548 generated article targets were checked on disk. Production checkout is
pinned to `d63b93f`, while documentation receipts may advance the task branch.
