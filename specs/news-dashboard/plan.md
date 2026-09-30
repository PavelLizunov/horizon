# News Dashboard Integration Plan — proposed v1

## 1. Evidence and architecture choice

Current facts from owning code:

- `SummaryItemView` already contains title, anchor ID, analysis, and artifact;
  `DailySummaryView` provides resolved profile grouping. Search documents already
  use `{date}-{language}-{slug}` and current article URLs.
- `ArticlePage` currently carries only slug/Markdown/title. `publish_site_pages`
  writes title/search-exclusion front matter and prunes stale issue pages after
  successful writes. `write_site_index(limit=60)` is an issue listing, not a feed.
- Frozen summaries retain anchors, scores, leads, tags, and profile identifiers.
  The existing archive parser in `dev_reindex_archive.py` and republisher already
  understand this format; neither should be duplicated as a new regex parser.
- The daily script's ship-only mode returns before ordinary metadata regeneration.
  The narration fix invokes this mode after successful attachments. Generating
  feed metadata only once after the pipeline would leave audio flags stale.
- Material uses instant navigation and owns the palette. Existing player code
  subscribes to `document$`. The new dashboard must do the same idempotently.
- Installed site tool: MkDocs 1.6.1. Native hook support exists since 1.4;
  see [MkDocs hooks](https://www.mkdocs.org/user-guide/configuration/#hooks).

**Choice:** extend existing static MkDocs output with a small build hook and
progressive-enhancement JS. Reuse the approved visual design; do not ship prototype
React/Babel as a production dependency, and do not create a new news API or SPA.
An installed native hook is enough; a custom plugin package is not warranted.

## 2. Canonical article metadata and legacy coverage

1. Add optional dashboard metadata to `ArticlePage`, preserving existing
   construction/callers. Populate it from the same resolved summary view used
   for article titles/slugs, not raw `item.profile`.
2. Persist a namespaced, versioned `dashboard` front-matter mapping alongside
   existing title/search keys. This lives with the published page; stale article
   pruning therefore also removes catalog candidates without a second database.
3. Build the catalog from all eligible article files registered in the MkDocs
   build; ignore issue index/aggregate pages, validate IDs and dates, and verify
   referenced page output routes. No secret config is needed by the site hook.
4. Metadata fallback for existing pages/legacy summaries reuses the current
   archive parser. If reuse needs extraction from the dev script, move only pure
   parsing helpers to an owning module and keep the script imports/API compatible.
5. Inventory legacy formats and parser coverage using local read-only counts,
   never publishing private archive contents into task records. Add fixtures for
   both rendered and frozen formats. Merge by existing ID, prefer explicit page
   metadata, and emit diagnostics for mismatches/unparsed real articles.
6. Do not rerender old article bodies to backfill card metadata: that could erase
   attached audio or verification text. A build-time fallback/metadata-only backfill
   preserves bodies and URLs. Before rollout, every supported published page must
   resolve; remaining legacy formats are a named blocker, not silently skipped.
7. Teaser uses existing lead/analysis text, never the private reasoning field.
   Reading time is a labeled approximation of public text. Tags/source/score may
   be absent. No hallucinated source labels or scores.

## 3. Build hook and static fallback

Use one stdlib-compatible, dependency-light hook file outside the public docs tree
(the site tool runs in its own venv, so it must not import the entire application
or require application-only Pydantic dependencies). Keep catalog/selection helpers
separately testable if necessary; avoid a framework for this small hook.

- Read source metadata once at the build's file/page event; compute catalog and
  focus selection. Produce a server-rendered homepage during page rendering, so
  headline links/cards are present even without JS. Do not rewrite tracked live
  `docs/index.md` with runtime news or make another generated-placeholder trap.
- Write the compact, versioned JSON into `site_dir` after the build (or register
  it as a generated MkDocs File after validating the installed native API).
  Final hook event/API choice must be verified in a scratch fixture build before
  implementing; it must work for clean build and instant navigation.
- Read attached validated audio markup from the page to derive `audio_ready`.
  Do not probe storage/network, transcribe audio, or consider leftover local Opus
  files a publication signal.
- Every normal `mkdocs build` regenerates static cards and catalog. This includes
  initial text publish, ship-only, per-article narration hook, and final refresh;
  no special new daily service or nested paid run is needed.
- Invalid individual entries are diagnosed. If a valid nonempty published archive
  unexpectedly yields no catalog, fail the local build before transfer rather
  than publish a misleading empty homepage. Truly empty clean clones render a
  normal empty state. Browser data failure leaves server-rendered cards intact.

## 4. UI and existing-site integration

- Small homepage-specific Material override via `theme.custom_dir` to remove the
  document sidebar/TOC and give the dashboard full width, retaining shared site
  header/navigation and theme toggle. No duplicate prototype header on top of
  Material. Article page layout remains unchanged.
- New top-level `horizon-dashboard.css` and `horizon-dashboard.js`, scoped classes;
  leave the large existing digest stylesheet and legacy assets mostly untouched.
  Host licensed Plex fonts locally, with robust fallbacks; no runtime CDN.
- Five focus tiles and an initial feed of 24 cards; a real button progressively
  appends another 24 from the full compact catalog. Stable sorts/filters render
  only the currently requested batch, not thousands of DOM nodes.
- First load has useful SSR content; JS adds search, sorts, topics, period,
  saved/recent views, and URL query state so browser Back restores navigation.
  Full-text search stays at the existing search page and successful API contract.
- Links remain `<a>` to real article pages: new tabs, history, copying links and
  no-JS navigation work. Do not replace actual content with demo-dialog prose.
- Save button appears on cards and actual article pages. Record recent history
  on article-page visits, not merely on homepage click, covering Telegram/direct
  links/new tabs and Material instant navigation. Event binding is idempotent.
- Use a versioned production localStorage namespace different from the prototype;
  bounded saved/recent lists (proposed 500/100), resilient malformed/quota/disabled
  storage handling. Store minimal validated IDs/snapshots; handle removed articles
  explicitly, never lead users to a known-dead page. Offer removal/clear actions.
- Reuse Material's palette instead of a second theme preference; test both palettes,
  restored filters, keyboard focus, popstate and reduced-motion behavior.

## 5. Vector cover system

Reuse the five approved design families and extend mapping to actual profile IDs:
chip/local computation, orbits/agents, server/infrastructure, network/routes,
wave/research. Provide coherent finance, video/speech, community/gaming and generic
fallback as needed by the active catalog; do not hardcode real deployment profiles
or hide unknown topics. Prefer a small checked mapping with a fallback over AI
classification or a cover DSL.

Trusted SVG templates only. Article ID deterministically selects a modest palette
and composition variant, so not every card in one topic is identical. No randomized
change on reload; no uncontrolled text inserted into SVG. Headline remains actual
HTML text. Keep leading image proportions and reserved layout space; reuse shared
assets/symbols where the markup benefit is real. Covers must remain decorative,
not depict unverified event facts, and must be available before first publish.

## 6. Delivery sequence and reviews

A. Contract + fixtures + archive inventory. Approve IDs/schema, hero defaults,
   metadata precedence, and existing caller compatibility before behavioral edits.
B. Catalog/legacy compatibility + deterministic selection + hook proof in a
   scratch MkDocs build. Verify live build, clean clone, stale pruning, audio flags.
C. UI + SVG integration in a separate local/staging build with actual or sanitized
   archive data. Remove all demo labels/stories/control-panel artifacts in production.
D. State + history on real article pages; keyboard/mobile/instant navigation checks.
E. Full offline tests, scoped review, docs/guides, task branch commit/push, owner
   preview. No production readiness claim based solely on test count.
F. Owner-approved deployment: confirm active job/timer state and installed build
   versions, apply verified commit without overlapping publishers or restarting DSH,
   rebuild/ship without running fetch/LLM/narration, inspect exact public routes.
   Preserve old deploy artifact for rollback. The existing remote replacement is
   non-atomic; highlight that risk and agree the deployment window. Do not silently
   expand this change into ingress hardening.

Current design branch contains the earlier narration fix. Plan the integration
base deliberately: merge approved narration work first or use a reviewed base
that preserves it. Never cherry-pick/merge incidental config/profile changes.

## 7. Verification matrix and provisional budgets

| Area | Evidence needed |
|---|---|
| Metadata/schema | Valid and malicious fixtures, old ArticlePage callers, finite/null score, safe paths, no private reasoning/cost/status fields. |
| Archive | Modern/frozen/unsupported samples, zero duplicate IDs, no fabricated omissions, only actually published page targets, preserved audio/body. |
| Focus | Deterministic ties, topic diversity, repeated URL exclusion, 7/30/all widening, missing scores, fewer than five items. |
| Build | Native-hook scratch build with installed MkDocs 1.6.1, clean clone empty state, stale page pruning, homepage SSR links, generated file copied correctly, no live archive committed. |
| Narration coupling | Initial audio false; attached passed track + ship-only rebuild true; failed track remains false; text-first and no recursive pipeline. |
| Browser | Search/sorts/filters/show-more, state restoration, bookmarks/direct-link history, clear actions, storage faults, JS disabled, catalog error/retry, duplicate navigation handlers. |
| Visual/accessibility | Compare to approved prototype at 1440/768/390/320px; light/dark, 44px targets, no overflow, focus order, reduced motion, player coexistence, local fonts. |
| Operational | Public homepage/old links/archive/full-text search/checks, actual asset hashes/cache policy and rollback route. Network reachability verified separately from host-local checks. |

Measure catalog bytes, build time, and render/filter duration on sanitized actual
archive size before sealing the implementation. Provisional gates: full catalog
<=2 MiB uncompressed, first DOM batch <=29 cards (5+24), p95 filter/sort/render
<=150ms on the recorded test environment, metadata generation <10% of measured
site-build time. These are targets, not observed results or guarantees for phones.
If size/timing budgets fail, propose bounded manifest/chunk loading in an explicit
plan revision, without quietly truncating history or adding a new backend.

## 8. Expected change map

Names of new files are provisional until the hook proof, but ownership is bounded:

| Area | Expected changes |
|---|---|
| Rendering/storage | `src/ai/summarizer.py` (optional metadata), `src/storage/manager.py` (additive front matter); pure shared archive parser only if required for reuse. |
| Pipeline coupling | `src/orchestrator.py` only if passing resolved metadata requires it; no pipeline stage ordering/provider changes. |
| Static build | `mkdocs.yml`, one native hook under `deploy/` or a dedicated site-build directory, homepage-only Material override under `docs/overrides/`. |
| Homepage/assets | `docs/index.md`, new top-level dashboard CSS/JS/SVG assets and local fonts; update ignored generated catalog rules only if a docs-tree output is needed. |
| Article controls | Additive save/history UI in existing article markup or its small client enhancement; no body/player redesign. |
| Legacy scripts | Only parser extraction/import changes with preserved behavior in the reindex/republish scripts; no indexing/network run as a test. |
| Verification/docs | New dashboard tests and native-hook fixtures, existing caller regressions, owning README/guides and publishing/narration documentation where coupled. |

Prototype assets remain under `opendesign/` as review evidence, not copied wholesale
into the public docs tree. Runtime React bundles, demo stories and verifier tools
are not needed in production. A frozen-versus-live identity snapshot in tests must
show unchanged IDs/links after metadata migration.

## 9. Remaining unknowns

Actual archive count/formats and missing metadata, cross-profile score calibration,
profile display labels, installed MkDocs versions on every supported publisher,
Material rendering override compatibility, public cache behavior, and current
production checkout relative to the narration branch. None authorizes paid/model
runs or a deployment during this planning task.
