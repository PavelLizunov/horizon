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
  or dependency. Native hook events verified in isolated MkDocs fixture builds.
- Defaults implemented and verified on the task branch; production remains unchanged.

## Phase A — contract and coverage (D1, D2, D4, D7, D9)

- [x] Owner approves this implementation scope, focus defaults, static catalog v1,
      vector-only covers, and browser-local state.
- [x] Establish task branch base and preserve the verified narration fixes;
      exclude unrelated config/profile changes.
- [x] Inventory published Russian archive format/counts locally; record coverage
      counts without committing private article contents or runtime config.
- [x] Add synthetic modern/frozen/invalid/malicious/missing-score fixtures.
- [x] Validate legacy metadata precedence and ID/URL compatibility with every
      supported format; explicitly resolve unsupported real formats.

## Phase B — catalog and build (D1, D2, D7, D8, D9, D10)

- [x] Add optional metadata to ArticlePage and versioned namespaced front matter,
      based on resolved SummaryItemView/DailySummaryView values.
- [x] Reuse pure archive parser helpers; preserve existing script contracts and
      do not rerender historical audio/verification bodies for metadata backfill.
- [x] Implement safe catalog serialization and deterministic focus selection.
- [x] Prove native hook events/registered output in a scratch MkDocs build using
      the site's isolated interpreter; avoid application-heavy imports.
- [x] Integrate hook-rendered static homepage and complete compact JSON catalog.
- [x] Test clean clone, empty history, bad-entry diagnostics, invalid-empty guard,
      stale page pruning, and all article path targets.
- [x] Test ship-only/per-article narration rebuild updates audio metadata without
      any paid pipeline/model calls or new scheduler.

## Phase C — visual homepage (D2, D3, D4, D6, D8, D11)

- [x] Add homepage-only Material override, scoped CSS/JS, and licensed local fonts.
- [x] Reuse approved SVG families; add deterministic variants/profile mappings
      and generic fallback. Keep all source text out of raw SVG commands.
- [x] Implement five focus cards, 24-card feed batches, actual page links, and
      access to archive/search/collection/checks.
- [x] Implement newest/score sorting, real profile filters, periods, local search
      and explicit full-text search handoff with query preservation.
- [x] Implement URL/back navigation state, empty/error/retry and static no-JS fallback.
- [x] Compare production-integrated preview to approved mockup at all breakpoints;
      no demo news/control panel or duplicate Material headers on the public page.

## Phase D — return-to-reading features (D5, D8, D11)

- [x] Bookmark buttons on both cards and real article pages, bounded state, remove
      and clear controls, minimal safe snapshots and missing-article handling.
- [x] Record history on direct/Telegram/new-tab page visits and instant navigation.
- [x] Use isolated versioned production storage namespace; handle corrupt/blocked/
      quota-exceeded storage visibly without breaking reading.
- [x] Reuse Material theme; verify focus, keyboard, reduced motion, touch targets,
      idempotent subscriptions, and unchanged narration player behavior.

## Phase E — acceptance and backup (D1–D11)

- [x] Offline unit/contract/regression tests pass for the changed version; full suite.
- [x] Native MkDocs build verified with scratch output and sanitized real-size data;
      catalog/build/render measurements satisfy agreed budgets or plan is revised.
- [x] Browser tests: all UI actions, persistence/URL navigation, JS disabled,
      missing catalog, storage faults, dark/light and 1440/768/390/320 widths.
- [x] All catalog links resolve; coverage and legacy omissions explicitly reviewed.
- [x] Scoped correctness/security review: escaping, paths, SVG allowlists, JSON
      embedding, no private data leaks, no injected commands or API expansion.
- [x] Update owning README, local guides, publishing spec references and docs;
      generated live news/catalogs never committed.
- [x] Commit/push task-only changes and provide owner preview + verification record.

## Phase F — separately approved rollout

- [ ] Obtain deployment authorization/window; check active publishers, timers,
      exact checkout and supported MkDocs versions. No DSH restart.
- [ ] Preserve rollback artifact, apply verified commit and rebuild/ship without
      fetch/LLM/narration, with no overlapping publishers.
- [ ] Verify exact public homepage, old article/anchor links, archive/search,
      checks/collection, local assets, audio flags, and cache freshness.
- [ ] Verify rollback path and report measured results/remaining limits.


## Implementation evidence

Implementation commit `e431a86`, pushed to `origin/feat/news-dashboard`.
890 offline tests and 34 browser checks passed. Native builds cover empty, real
3-article, 90-item and 1000-item archives. Evidence/limits are in
[verification.md](verification.md). The managed Tailnet preview remains available;
its runtime articles/screenshots are ignored and not pushed. Production rollout
checks above remain deliberately pending and require separate authorization.
