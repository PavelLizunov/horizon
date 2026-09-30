# News dashboard

The homepage is built from **published Russian article pages**, not from scraped
items or search results. It uses the existing MkDocs build and requires no new
service or model. The archive and full-text search keep their existing URLs.

## Reading and returning

- **В фокусе** shows up to five distinct stories. It starts with seven days from
  the latest available issue, widens to 30 days/history when necessary, and
  balances actual profiles before filling remaining slots. Scores are interest
  ratings, not factual verification scores. Missing scores are not invented.
- **Свежие / По рейтингу**, profile and period filters work over the full compact
  catalog. The default feed starts with 24 additional cards; **Показать ещё** adds
  another 24. Focus cards are excluded only in the unfiltered default feed.
- Local text search matches title, teaser, topic, tags and source label. The link
  to **Поиск по архиву** carries the query to the existing full-text search page.
- **Отложенное** and **История** use browser-local storage. Article pages offer a
  save button and record visits, including direct Telegram links. These lists do
  not synchronize across devices. Clear actions ask before deleting local lists.
- Unknown or removed articles are shown as unavailable saved/history records with
  a remove action. Blocked storage leaves the current session usable and displays
  a notice; it does not prevent reading.

## Data and builds

`ArticlePage.dashboard` is optional additive metadata. New pages store versioned
`dashboard` front matter alongside the existing title and search exclusion. The
native hook `deploy/dashboard_hook.py` reconstructs older cards from already
published article bodies and issue-index labels, preserving their text/audio/URLs.
It shares the pure frozen-heading parser from `src/storage/archive.py`; it never
loads runtime secrets/configuration or calls Elasticsearch/LLMs.

Every `mkdocs build` writes `assets/dashboard/catalog.json` into the **build output**,
not the source docs or Git. The catalog is schema version 1, includes public card
fields and `focus_ids`, and contains neither full article bodies nor private
reasoning, costs, token usage or operational verification errors. Failed parsing
of an eligible published article fails the local build before any deployment;
a clean clone with no articles renders an honest empty state.

Audio readiness comes only from attached narration markup. Thus ship-only builds
and narration's per-article site refresh automatically update the homepage without
rerunning the paid pipeline or adding a scheduler.

The hook runs in the site's separate MkDocs environment using its existing YAML
loader and stdlib-only catalog/parser helpers. It does not import the application
AI clients or require the project venv. Verified locally with MkDocs 1.6.1.

## Styling and fallback

A homepage-only Material override provides full-width tiles; normal article pages
keep their existing layout and player. Scoped dashboard CSS/JS reuses Material's
palette and instant navigation. Licensed IBM Plex fonts and eight decorative SVG
families are local assets. Article IDs pick deterministic composition/color
variants; no image generator or remote font/CDN is involved.

Initial cards and ordinary article/archive links work without JavaScript. A failed
catalog request leaves these cards visible and offers retry. Interactive controls
become available only after a valid catalog loads.

## Verification and rollback boundary

Run the offline dashboard/storage/search/summarizer tests and a native MkDocs build
into a scratch directory. Browser checks must cover no-JS links, theme/contrast,
instant navigation, local storage faults, missing catalog and mobile overflow.
Do not use `deploy/run-daily.sh` as a local build check: even ship-only mutates the
live site. Production application requires a separate deployment window and a
retained previous artifact; ingress replacement remains non-atomic.
