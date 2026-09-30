# News Dashboard Tasks

## Planning record

- Implementation authorized by the user's «Начинай»; production deployment remains
  outside authorization. Branch `feat/news-dashboard` descends from plan commit
  `57e8bae`, preserving prototype and narration fixes. Unrelated user changes remain
  unstaged. Local inventory: 3 published Russian articles, 1 issue, all with attached
  audio, none with dashboard front matter. No archive body is copied into records.
- Inspected published-page/storage contracts, resolved summary view, search
  identity/schema, frozen archive parser/republisher, ship-only/narration flow,
  Material palette/instant navigation, and the approved prototype.
- Verified available site build tool: MkDocs 1.6.1; native hooks avoid a new service
  or dependency. Hook event details remain an implementation proof task.
- Defaults proposed in spec/plan, not already active site behavior.

## Phase A — contract and coverage (D1, D2, D4, D7, D9)

- [x] Owner approves this implementation scope, focus defaults, static catalog v1,
      vector-only covers, and browser-local state.
- [ ] Establish task branch base and preserve the verified narration fixes;
      exclude unrelated config/profile changes.
- [ ] Inventory published Russian archive format/counts locally; record coverage
      counts without committing private article contents or runtime config.
- [ ] Add synthetic modern/frozen/invalid/malicious/missing-score fixtures.
- [ ] Validate legacy metadata precedence and ID/URL compatibility with every
      supported format; explicitly resolve unsupported real formats.

## Phase B — catalog and build (D1, D2, D7, D8, D9, D10)

- [ ] Add optional metadata to ArticlePage and versioned namespaced front matter,
      based on resolved SummaryItemView/DailySummaryView values.
- [ ] Reuse pure archive parser helpers; preserve existing script contracts and
      do not rerender historical audio/verification bodies for metadata backfill.
- [ ] Implement safe catalog serialization and deterministic focus selection.
- [ ] Prove native hook events/registered output in a scratch MkDocs build using
      the site's isolated interpreter; avoid application-heavy imports.
- [ ] Integrate hook-rendered static homepage and complete compact JSON catalog.
- [ ] Test clean clone, empty history, bad-entry diagnostics, invalid-empty guard,
      stale page pruning, and all article path targets.
- [ ] Test ship-only/per-article narration rebuild updates audio metadata without
      any paid pipeline/model calls or new scheduler.

## Phase C — visual homepage (D2, D3, D4, D6, D8, D11)

- [ ] Add homepage-only Material override, scoped CSS/JS, and licensed local fonts.
- [ ] Reuse approved SVG families; add deterministic variants/profile mappings
      and generic fallback. Keep all source text out of raw SVG commands.
- [ ] Implement five focus cards, 24-card feed batches, actual page links, and
      access to archive/search/collection/checks.
- [ ] Implement newest/score sorting, real profile filters, periods, local search
      and explicit full-text search handoff with query preservation.
- [ ] Implement URL/back navigation state, empty/error/retry and static no-JS fallback.
- [ ] Compare production-integrated preview to approved mockup at all breakpoints;
      no demo news/control panel or duplicate Material headers on the public page.

## Phase D — return-to-reading features (D5, D8, D11)

- [ ] Bookmark buttons on both cards and real article pages, bounded state, remove
      and clear controls, minimal safe snapshots and missing-article handling.
- [ ] Record history on direct/Telegram/new-tab page visits and instant navigation.
- [ ] Use isolated versioned production storage namespace; handle corrupt/blocked/
      quota-exceeded storage visibly without breaking reading.
- [ ] Reuse Material theme; verify focus, keyboard, reduced motion, touch targets,
      idempotent subscriptions, and unchanged narration player behavior.

## Phase E — acceptance and backup (D1–D11)

- [ ] Offline unit/contract/regression tests pass for the changed version; full suite.
- [ ] Native MkDocs build verified with scratch output and sanitized real-size data;
      catalog/build/render measurements satisfy agreed budgets or plan is revised.
- [ ] Browser tests: all UI actions, persistence/URL navigation, JS disabled,
      missing catalog, storage faults, dark/light and 1440/768/390/320 widths.
- [ ] All catalog links resolve; coverage and legacy omissions explicitly reviewed.
- [ ] Scoped correctness/security review: escaping, paths, SVG allowlists, JSON
      embedding, no private data leaks, no injected commands or API expansion.
- [ ] Update owning README, local guides, publishing spec references and docs;
      generated live news/catalogs never committed.
- [ ] Commit/push task-only changes and provide owner preview + verification record.

## Phase F — separately approved rollout

- [ ] Obtain deployment authorization/window; check active publishers, timers,
      exact checkout and supported MkDocs versions. No DSH restart.
- [ ] Preserve rollback artifact, apply verified commit and rebuild/ship without
      fetch/LLM/narration, with no overlapping publishers.
- [ ] Verify exact public homepage, old article/anchor links, archive/search,
      checks/collection, local assets, audio flags, and cache freshness.
- [ ] Verify rollback path and report measured results/remaining limits.
