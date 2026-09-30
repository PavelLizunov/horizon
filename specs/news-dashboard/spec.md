# News Dashboard Specification — proposed v1

## 1. Status and intended result

Implementation approved by the user's «Начинай» following the reviewed plan.
The editorial prototype, static catalog v1, selection defaults, vector-only covers,
and browser-local state are the baseline. Production deployment is not approved.
Replace the explanatory homepage with a usable news dashboard matching the approved
prototype: one lead tile, four supporting tiles, and an archive-spanning feed.
Use deterministic vector covers, not a generative image model, in v1.

## 2. Scope and compatibility

- Preserve the name, penguin, editorial composition, local Plex fonts, light/dark
  themes, and mobile layout. Keep archive, collection, checks, and full-text search
  accessible from navigation; do not replace the site with another application.
- Keep existing article/issue URLs, old aggregate anchors, and `/api/search` and
  `/search` contracts unchanged. Normal article links open existing full pages,
  not the prototype's demonstration dialog. No article redesign in this scope.
- Reuse current profile classification and interest score. No new LLM calls,
  reranking model, account system, backend service, scheduler, or GPU dependency.
- Catalog only published article pages, never scraped-but-unpublished items.
  Runtime archive/state, secrets, and generated live catalogs remain uncommitted.
- This dashboard is a separate extension to site publishing; do not rewrite
  historical site-publishing decisions. Update owning guides/docs on implementation.

## 3. Reader behavior and acceptance criteria

| ID | Requirement | Acceptance |
|---|---|---|
| D1 | Real archive feed | Every eligible published article has one stable issue-scoped ID and a working internal link; no demo content or invented score. |
| D2 | Five focus tiles | Pick up to five distinct sources/stories across topics deterministically; render fewer honestly if insufficient content. |
| D3 | Browsing | Newest/score sorts; topic/profile filter; 7 days, 30 days, all-time periods; incremental batches of 24 cards, with no omission from the searchable catalog. |
| D4 | Finding old articles | Local search over title, teaser, topic, tags, source. Explicit link to existing full-text archive search; do not imply local matching searches the entire article body. |
| D5 | Saved/recent | Browser-local bookmarks and recent history work on both dashboard and directly opened article pages, persist across reload, and can be individually removed or cleared. No implied cross-device sync. |
| D6 | Vector covers | Trusted local SVG templates chosen by actual profile/topic and stable article ID, with coherent variations and generic fallback for future profiles. No scripts, remote images, or network generation. |
| D7 | Audio availability | Display audio-ready only when a validated attached player exists in the article. Every site rebuild refreshes this metadata; no age- or file-existence guessing. |
| D8 | Robustness | Without JS, initial cards, article links, archive/search links work. JSON-load or storage failure must not hide the static content. Clear loading/empty/error/retry states. |
| D9 | Safe output | HTML-escape data, validate local page paths, keep untrusted text out of SVG/HTML commands, sanitize teaser markup. No internal verification errors, usage, tokens, or cost fields in catalog. |
| D10 | Publication | Text-first publication remains unchanged; no cover-generation wait. Ship-only and per-article narration refresh regenerate the dashboard automatically. |
| D11 | Integration | Works with Material palette and instant navigation without double event handlers, duplicate headers, missing history entries, or player conflicts. Keyboard focus and 44px touch targets preserved. |

### Focus selection defaults (proposal)

1. Candidates: Russian published articles within seven calendar days of the newest
   available Russian issue. Anchor to available content, not the machine clock,
   so a quiet archive does not produce an empty focus section.
2. Collapse repeated source URLs for the focus selection only; archived occurrences
   remain separately discoverable. When URL is absent, compare normalized title.
3. Order scored candidates by score descending, date descending, stable ID.
   First select one per actual profile; fill remaining slots from that order,
   preferring at most two per profile before relaxing if necessary.
4. If fewer than five candidates, extend to 30 days, then all available history.
   Unknown-score articles remain browsable and fill gaps only after scored ones.
5. Cards show real dates; never label older fallback articles as today's news.
   Focus is the unfiltered default view. Any filter/query/score sort gives a normal
   feed across the chosen scope, with no hidden hero exclusions.

Interest scores across profiles may not be perfectly calibrated. Present them as
interest/relevance scores, never as reliability or factual verification scores.

## 4. Catalog contract (new additive static surface)

`schema_version: 1`, `generated_at` (UTC), `items` array, optional diagnostic counts
for build logs only. Public item fields:

- `id`: `{issue-date}-{language}-{slug}` (existing issue-scoped identity).
- `page`: validated site-relative directory URL; `date`: issue date,
  `language`, `profile_id`, and reader-facing `profile_name`.
- `title`, `teaser` (plain text, at most 240 characters), `tags` (bounded list),
  optional reader-facing `source_label`; unknown values are omitted, not fabricated.
- `score`: finite 0–10 number or null; `reading_minutes`: approximate visible
  article reading time, not audio duration; `audio_ready`: boolean.
- `cover_key`: allowlisted template family and stable variation seed. Catalog
  must not contain arbitrary SVG/HTML, provider config, or remote commands.

The catalog covers all published Russian pages supported by the parser, not just
60 issues (the current archive listing limit). Unsupported/invalid legacy entries
are counted and investigated before rollout; do not silently call partial backfill
complete. Existing other-language articles/URLs remain available in the archive.
No public live catalog is committed; clean clones build a truthful empty state.

## 5. Exclusions and owner decisions

Not in v1: model-generated covers, personalized ML ranking, accounts/cloud sync,
full-text client index, a new search API, continuous live feed, article styling
redesign, atomic ingress replacement, or unrelated narration/provider changes.

Approval of this plan should cover proposed focus selection and static catalog
contract, plus required driver/template/script changes. Production application
requires a separately agreed deployment window; no restart is implied. Article
IDs currently depend on existing issue slugs; renaming/reordering historical slugs
is prohibited, not solved by a speculative new identity system.
