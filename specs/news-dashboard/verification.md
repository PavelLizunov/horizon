# Dashboard implementation verification

## Scope and version

In-session verification of the approved static dashboard implementation on branch
`feat/news-dashboard`. Production publishing and service restarts were not run.
The exact public production cache/deployment/legacy coverage must still be checked
in the separately approved rollout.

## Automated and build evidence

- Dashboard metadata/hook regressions: 28 passed. Covers modern-page fallback,
  frozen linked headings, stable IDs, profile labels, JSON-safe additive front
  matter, missing scores, source/path safety, private-field exclusion, focus
  diversity/dedup/period widening, unknown-score ordering, clean empty state,
  rejected partial coverage, duplicate IDs, safe embedded JSON, and audio refresh.
- Full offline suite on the changed version: **890 passed in 7.75 s**. Python
  compilation, JS syntax, and whitespace checks passed.
- Native build with MkDocs 1.6.1 in its isolated venv: local published catalog
  includes all 3 eligible articles, with 3 working unchanged article targets and
  attached audio flags. Catalog generation 0.003–0.004 s; build 0.24–0.25 s in
  repeated runs. No source article bodies were rewritten.
- Scratch empty/90/1000-article builds passed twice using synthetic data, not copied
  private news. 1000-item compact catalog is 523,761 bytes. Full build wall time
  was 2.800–2.801 s (includes tool startup). No truncation of history.
- Browser 1000-item sample: 29 initial card nodes (5+24), 30 alternating sort/render
  samples with forced layout; median 6.7 ms and p95 8.4–8.9 ms. Targets of <=2 MiB
  catalog, <=29 initial cards and <=150 ms p95 are met in this environment. These
  are local Chromium timings, not phone/production speed guarantees.

## Browser acceptance

Local Chromium headless build 1228; temporary Playwright/axe tools outside the
repository. 34 main checks passed, including:

- Actual catalog coverage and every local article URL.
- Five focus tiles using a synthetic 90-item response; 24-card first batch and
  48-card show-more output; score order and browser Back filter restoration.
- Title search and full-text query handoff; empty saved list, save/reload, article
  save from direct visit, real article history and instant navigation without
  duplicate history entries; individual removal and clear-history confirmation.
- No horizontal overflow at 1440/768/390/320 px.
- Targeted light/dark axe checks for contrast, named buttons/labels/image alt and
  valid ARIA values: no violations after correcting inherited theme styles.
- No-JS page retains real article links. Failed catalog retains static cards,
  suppresses unusable save buttons and supports retry.
- Blocked localStorage retains session saves, exposes a truthful warning, and does
  not break reading. No uncaught page errors.
- Bookmark keyboard focus restoration checked separately after card rerender.

Screenshots are under ignored `opendesign/previews/news-dashboard/` (desktop,
mobile, dark). The Tailnet-only artifact server is managed job `bash-106`; the
integrated route is separate from the approved prototype. Client-side reachability
from the user's device has not been confirmed. No full accessibility audit,
physical-device touch test, or actual audio playback was performed in this task;
existing narration/player tests remain unchanged.

## Scoped review

- Server catalog is field-allowlisted, finite/null scores, validated article route,
  versioned metadata. It reads only published page content and public issue labels,
  never live config/credentials or private model reasoning.
- Raw source URLs are internal dedup inputs, omitted from public catalog; card
  labels are escaped and trusted SVG files contain no external/script references.
- Article JSON escapes `<`, `>` and `&` to prevent a closing-script injection.
  JS checks route/ID/schema fields and escapes all text before rendering.
- Unknown published formats/duplicate IDs fail the local build before transfer;
  stale pruning removes absent pages from subsequent catalog builds.
- Hook handles all site builds, so ship-only narration refresh rederives attached
  audio flags with no recursive paid run. No search API/provider changes.
- Pure legacy parsing moved without algorithm changes; existing archive import
  surfaces `_split_blocks` and `parse_summary` remain compatible.
- No authorized explicit-model independent review route was used; correctness/
  security review was performed in-session. Production archive is not available
  locally beyond 3 articles; rollout must confirm its complete parser coverage.
