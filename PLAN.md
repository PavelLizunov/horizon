# Work plan — site publishing, Telegram delivery, model A/B

Living checklist. **Mark each step done as you finish it and commit that mark
with the work.** Any agent — Claude, Codex, Qwen — can pick this up mid-way:
read `AGENTS.md` first for the invariants, then find the first unchecked box.

Delete this file when everything is checked and shipped.

## How to work this file

```bash
uv run --offline python -m pytest tests/ -q    # must stay green; 561 at time of writing
```

- Every behaviour change ships an offline test. No network in tests.
- Never run `horizon` to "check it works" — it costs real LLM money
  (measured: 259 942 tokens / 11 items per run). `pytest` and
  `scripts/dev_check_*.py` are free. See `AGENTS.md` §3.
- Minimal, surgical diffs: upstream actively edits `src/orchestrator.py` and
  `src/ai/`, and this fork stays merge-friendly.
- Commit per step, message explaining *why*, not just *what*.
- GitHub is unreachable from the Windows workstation; the Mac pushes. See
  `deploy/RUNBOOK.md`.

---

## Context

The digest (38 461 chars, 11–50 items) cannot go to Telegram: the message cap
is 4 096 chars and every unsupported tag (`<details>`, `<ul>`, `<li>`, headings,
`<a id>` — all present) makes Telegram reject the whole message rather than
degrade it.

Plan: full digest to a self-hosted **MkDocs Material** site at
`digest.ninitux.com`; **headlines only** to Telegram, deep-linked to the
per-item anchors the digest already generates.

Two findings that shaped this, both measured — do not re-derive:

- **The current Jekyll path publishes nothing.** `docs/_posts/*.md` is
  gitignored and `deploy-docs.yml` only fires on committed `docs/**` changes, so
  the digest has never reached GitHub Pages. This is greenfield, not a migration.
- **Anchors survive markdown rendering.** Measured on the real digest: 30 in,
  30 out, zero dangling TOC links. `<a>` is inline so Python-Markdown passes it
  through; heading auto-ids are title slugs and cannot collide with `item-*`.

Decisions taken: subdomain `digest.ninitux.com` · search covers documentation
only · no RSS · Telegram sends all items, chunked.

---

## Phase A — site + Telegram

### [x] A1. Fix markdown escaping — `534b08c`

`src/ai/summarizer.py:20`. `html.escape(quote=True)` emitted `&#x27;` and the
next line escaped the `#` *inside* that reference → dead `&\#x27;`. Renders by
accident on the site, breaks in email, would break Telegram HTML. Changed to
`quote=False`; dropped `<`/`>` (unreachable) and `|` (not in Python-Markdown's
`ESCAPED_CHARS`) from `_MARKDOWN_SPECIAL`.

Also added the **anchor-survival regression test** — the contract the whole
feature rests on. `tests/test_summarizer.py`.

### [x] A2. Keep the bot token out of logs — `534b08c`

`src/services/webhook.py`. `redact_url` stripped query and fragment only, but
Telegram carries its token in the path. Worse: `_validate_url` formatted the raw
URL into an exception that reaches `send_failure`, which posts it as an
*outbound webhook body*. Both fixed.

### [x] A3. Publish the site page — `StorageManager.publish_site_page`

Delete the inline Jekyll block `src/orchestrator.py:311-350` (40 lines) and call
a new `StorageManager.publish_site_page(date, summary, language)` instead.

- Writes `docs/digest/{date}-{lang}.md` with front matter `search: exclude: true`
  (this is what stops the search index growing — see A4), then the summary
  **verbatim**. Drop the H1 stripping: MkDocs takes the page title from the H1.
- Reuse `safe_output_path` (`src/storage/manager.py:21`) and `_atomic_write_text`
  (`src/_file_utils.py`). The current block uses a bare `open()` and is not atomic.
- Resolve the path from a module constant, not CWD — `deploy/README.md:93`
  documents a crontab variant where a missing `cd` would silently relocate the site.
- **Remove the `except Exception` swallow.** Once Telegram links to the site, a
  failed write must not let the run send links to a page that does not exist.
  The outer handler at `:391` already sends a failure webhook.
- Same commit: delete `_generate_summary` (`src/orchestrator.py:1073-1098`) — no
  callers anywhere.
- Also generate `docs/digest/index.md`: glob, sort descending, list the last N.
- Add `docs/digest/` to `.gitignore`.

Tests: front matter shape, H1 preserved, path traversal rejected (mirror
`tests/test_storage.py:190`), atomic-replace failure preserves the destination
(`:202`).

### [x] A4. MkDocs configuration — verified with a real `--strict` build

All three offline-unverifiable questions answered by an actual build:
`exclude_docs` keeps the upstream Jekyll files out; `search: exclude: true`
works (9 documentation pages indexed, digest pages absent);
`validation: anchors: ignore` lets `--strict` pass while the raw
`id="item-tech-news-1"` anchor survives into the rendered HTML. Build 0.44 s.

Two pre-existing warnings had to be fixed to pass `--strict`:
`twitter-cookies.md` was in no nav, and `configuration.md` linked to
`../src/mcp/*.md`, which are source files rather than documentation pages —
now absolute GitHub links.

Note for whoever comes next: Material prints a banner warning that **MkDocs 2.0
will break all plugins and theme overrides with no migration path**. That is
Material's position on upstream MkDocs 2.0, not a problem with this setup today.
It reinforces the existing rule — keep customization in `mkdocs.yml` and CSS,
avoid theme overrides.

`mkdocs.yml` at repo root: material theme, `language: ru`, light/dark palette,
`pymdownx.details`, `toc` with `permalink`, explicit `nav`, `not_in_nav: digest/*`.

**Do not delete the Jekyll files** — `docs/_config.yml`, `_includes/`,
`feed-*.xml`, `assets/js/horizon.js`, `assets/css/horizon.css` are upstream's;
deleting them buys a merge conflict forever. Use `exclude_docs` (MkDocs 1.5+,
gitignore syntax).

Two files must change anyway: `docs/index.md` (Liquid loops render as literal
text and it is the site root, so it cannot be excluded) and
`.github/workflows/deploy-docs.yml` (trigger → `workflow_dispatch`).

**GitHub Pages needs no action.** Verified 2026-08-06: the `gh-pages` branch
exists, but `https://pavellizunov.github.io/horizon/` returns 404 — Pages is not
publishing it. An earlier note in this plan claimed the stale site would keep
serving; that was assumed, not measured, and it was wrong. Deleting the branch
is cosmetic.

Do **not** use Material's blog plugin: it derives URLs from title slugs, and our
Telegram deep links must be constructible before the page exists.
Do **not** convert anchors to `attr_list` (`### T { #item-x-1 }`): the idiomatic
MkDocs answer is wrong here, because `markdown_utils._ANCHOR_ID_RE` strips
`<a id>` for chat platforms but would leave literal braces in every Feishu card,
email and Telegram message.

**This step needs a real `mkdocs build` on the Mac** — the only part not
verifiable offline. Check three things: does `exclude_docs` work; is
`search: exclude` supported in the installed version (Insiders-only in Material 8);
does `validation.anchors` fail the build over TOC links to `#item-*` that are not
in `page.toc` (if so, drop `--strict` or set `validation: anchors: ignore`).

### [x] A5. Telegram headline delivery — code and tests done; live send needs a token

**Do not add a platform.** `platform: "generic"` already handles Telegram's
error shape, and `_render` builds the body from a dict template then
`json.dumps` (`webhook.py:327-328`), so escaping is correct. The right axis is
`delivery`.

- Add `"headlines"` to `validate_delivery` (`src/models.py:545`).
- One branch in `build_daily_summary_messages` before the final `return`
  (`src/services/webhook.py:565`), returning one message per chunk.
- The builder consumes `summarizer.build_view(items, lang)` — the same seam
  Feishu uses at `:399`/`:526` — never the rendered markdown. Per line:
  `<b>{group}</b>` and `{i}. <a href="{link_base}/{date}-{lang}/#{anchor}">{title}</a> {score}/10`.
  Only `<b>` and `<a href>`; nothing from `_format_item` participates, so the
  unsupported tags cannot physically enter the payload.
- Do **not** use `clean_app_summary_markdown` here: it flattens `<details>` but
  leaves `<h3>` and `**bold**`, which Telegram rejects.
- `html.escape(..., quote=False)` on titles and group names is mandatory —
  titles are LLM output over scraped content. One literal `<` rejects the message.
- **Chunk at ≤ 3 900 chars.** The earlier "1 108 chars, fits one message" figure
  was measured on 11 items; `digest.max_items` is 50 and a real 30-item digest
  renders to 4 660 chars. 30 items → 2 messages, 50 → 3. Far under ~20/min.
- Truncate each title to ~200 chars before escaping so one pathological title
  cannot produce an unsplittable line.
- Add `link_base: Optional[str]` to `WebhookConfig`; when unset fall back to
  `_safe_url(view_item.item.url)` so the feature works before the site exists.
- `disable_web_page_preview: true` is not optional.

Tests (`tests/test_webhook.py`): tag whitelist (regex every tag name out of the
payload, assert ⊆ `{b, a}`) — this is the test that turns "message rejected" into
a red CI line; a title with `<script>`/`&`/`"` yields no raw `<`/`&`; every chunk
≤ 3 900 and a 50-item view yields ≥ 2 chunks losing no headline; the href anchor
equals `DailySummarizer._item_anchor(profile_id, index)` asserted against the
real function; `link_base` unset falls back to the item URL; the `languages`
filter still applies.

### [x] A6. Documentation

`data/config.example.json` (loaded by `tests/test_mcp_service_smoke.py:66`),
`docs/configuration.md`, `README.md`, `CHANGELOG.md`, and a new
`docs/telegram-delivery.md` recording the measured limits so nobody re-researches
them.

Note for the Telegram setup section: use `url_env`, **never**
`${TELEGRAM_TOKEN}` inside `request_body` — `_expand_env_vars`
(`src/storage/manager.py:30-54`) expands at load and `save_config` (`:102`)
writes the model back, so running `horizon-wizard` would bake the secret to disk.

### [x] A7. Infrastructure — live at https://digest.ninitux.com/

No new container was needed. The existing Caddy ingress (LXC 210) already serves
static sites from `/srv/<domain>/` with a matching `conf.d/<domain>.caddy`;
`digest.ninitux.com` follows that pattern, and DNS was already covered by a
wildcard. Verified after reload: the new site returns 200 over TLS, and
`gs.ninitux.com` and `ninitux.com` still return 200.

Two things the plan got wrong, found by running it: `uv tool install
mkdocs-material` fails — material is a theme with no executable, the binary
comes from `mkdocs` — and the ingress has no `rsync`, so deployment uses `tar`
over ssh instead. Both corrected in `deploy/README.md`.

LXC on Proxmox + its own Caddy (`file_server` + `try_files`, four lines) + DNS
for `digest.ninitux.com`. **Do not reuse the `cdn` Caddy** — it fronts the VPN
masquerading on `ninitux.top` and has a history of port conflicts.

Deploy topology: Mac runs the pipeline → `mkdocs build` → `rsync -a --delete
site/ user@lxc:/srv/horizon/`.

Install the toolchain as an isolated tool on the Mac: `uv tool install
mkdocs-material`. **Do not add it to `pyproject.toml`** — it drags ~30
transitive deps into a 678 KB `uv.lock` that is a prime upstream conflict file,
for something the runtime never imports.

Accept: a few-second **404 window** — today's page reaches the LXC only after
`rsync`, which runs after the Telegram send. Only today's link is affected.

---

## Active work — VPN and censorship radar MVP

Owner priority changed on 2026-08-13: the deployed pipeline no longer uses the
Alibaba Token Plan. It is configured for paid `deepseek-v4-flash` through the
OpenCode Go endpoint with no provider fallback; `deepseek-v4-flash-free` is not
configured anywhere in the runtime.

### [x] V0. Add the two evidence-calibrated profiles

Added `vpn-engineering` and `censorship-watch` with hard exclusions, thresholds
of 6.5/7.0, a 5.9 ceiling for a single field report, alternative explanations
and explicit next-measurement guidance. Evidence labels belong to the separate
Evidence Ledger, not to article-generation prose.

### [x] V1. Preserve existing queries while adding the radar

GDELT and Google News now accept arrays while normalizing their legacy single
objects. This is required because production already has a finance Google News
query; replacing it to add the Russian VPN query would silently delete coverage.

### [x] V2. Add the bounded source set and balanced quotas

The MVP enables eight checked upstream release feeds, two checked official OONI
feeds, four checked public Telegram channels, one global GDELT query and one
Russian Google News query. VPN category groups admit at most 12 items without
limiting unmatched technology, finance or video items.

### [x] V3. Complete the first live OpenCode Go run

The owner enabled the China-hosted model endpoint and the 2026-08-13 recovery
run completed with paid `deepseek-v4-flash`: 118 unique inputs, 11 published
articles and five shadow-verified articles. Verification used 297,825 tokens
(31,744 cached input, 143,156 ordinary input, 122,925 output), estimated at
$0.054550 in DeepSeek list prices. No VPN item cleared the first-day thresholds,
so the source set stays bounded until more days show whether that is signal or
over-filtering. The run also added a hard failure when every AI analysis fails,
instead of publishing an empty "successful" issue. The optional pronunciation
review stays disabled after `deepseek-v4-pro` exhausted both 4,096- and
8,192-token response limits without completing its compact JSON; the measured
static lexicon and independent Whisper audio check remain active.

### [ ] V4. Make verification honest, fresh and incident-aware

The first OpenCode Go run proved that the shadow mechanics work but the public
meaning does not: four of five artifact audits failed, one successful audit
found 23 uncovered factual spans, and the site still described partial results
as completed. The accepted redesign keeps the safe fetch/hash/exact-locator
primitives and removes the false implication of a universal truth check.

- [x] V4a. Extract claims from the final reader-visible artifact. Remove the
  second same-model artifact audit; it was costly and could not make the first
  model independent. Any timeout/error is `check_error`; an empty claim set is
  `not_applicable`, never `completed`.
- [x] V4b. Fix event provenance so two genuinely independent reporting origins
  can satisfy the event gate. Exact copies remain one origin.
- [x] V4c. Publish type-aware wording: official announcement/release,
  independently corroborated event, primary/vendor quantity, anecdotal or
  not-checkable. Never flatten these to one `verified` badge.
- [x] V4d. Record `checked_at`, source age and `next_check_at`. Fresh events and
  rumours remain provisional and are marked for another look at 24 and 72 hours;
  a later daily observation advances incident state. Official announcements can
  be attributed to their primary source at once.
- [x] V4e. Add the smallest persistent incident state for `censorship-watch`
  and `vpn-engineering`: stable incident key, first/last seen, last checked,
  next check and `PROVISIONAL / CORROBORATED / DISPUTED / RESOLVED`. Daily article
  dedup is not incident state.
- [x] V4f. Remove the duplicate reader-facing fact-check vocabulary. The article
  may retain analysis prose, but only Evidence Ledger owns source-coverage
  labels on the site.
- [ ] V4g. Ship with offline tests, a strict site build and one bounded paid
  OpenCode Go canary. Record real latency, statuses, token usage and publication.

---

## Completed work — Evidence Ledger shadow MVP

Owner priority changed on 2026-08-11: complete the measured Evidence Ledger
shadow MVP before resuming B2–B4 or D1. The implementation contract and deferred
scope live in `docs/verification/implementation-spec.md`.

### [x] E0. Freeze the real integration contracts

Added the repository preflight, evidence methodology and reduced shadow-MVP
specification. The design uses the existing orchestrator, renderer, atomic-file
helpers and URL-safety path; SQLite, DAG planning, public labels, revalidation,
MCP and multimodal work are explicitly deferred.

### [x] E1. Make discovery failure explicit and fetch evidence safely

Added a typed search outcome while preserving the enrichment tool's legacy list
shape. Evidence downloads share the public-URL resolver, pin the validated IP
through redirects, inherit no credentials or cookies, and enforce wall-clock,
streaming byte, response-status and MIME limits. Failed automatic search falls
back through bounded explicit backends without hiding a total outage. Missing
MIME headers accept only strictly sniffed UTF-8 text. All tests are offline.

### [x] E2. Add the disabled-by-default shadow ledger

Added canonical fetched/selected snapshot IDs, immutable payload objects,
content-hashed JSONL revisions and an atomic run manifest. URL and topic dedup
both retain member maps, selected lineage resolves to every fetched snapshot,
and capture occurs after Twitter re-analysis/balancing but before enrichment.
Disabled mode writes nothing; shadow capture never changes publication output.

### [x] E3. Extract at most three anchored core claims

Technology-news shadow items now yield at most three headline/load-bearing
claims. The model copies an exact source span; code resolves a unique Unicode
locator against the immutable selected snapshot and derives the claim ID.
Schema-invalid responses retry; inexact/ambiguous proposals are discarded and
counted without throwing away exact siblings. Checkable, ambiguous and
not-checkable states remain explicit, and extraction failure never changes
publication.

### [x] E4. Retrieve and adjudicate evidence in shadow

Added deterministic primary/independent/counterquery templates, original-URL
fetching, strict per-claim query/document ceilings, cache accounting and the
guarded E1 fetch path. Search snippets remain discovery-only. Normalized
evidence snapshots and exact excerpt cards are persisted with conservative
copy/direct-record origin keys. A versioned truth table derives all six statuses
and records gates, coverage, failures, stop reasons and preliminary reports.
Inexact evidence excerpts are discarded and counted; any partial assessment is
forced to insufficient evidence. Nothing is reader-visible.

### [x] E5. Audit final artifacts and evaluate

Added a one-call, exact-span audit over every localized artifact title and block.
Unknown claim IDs and inexact locators fail closed; claims with verification
errors/not-checkable status do not cover generated prose. Unmatched spans and
matched evidence IDs are recorded without mutating artifacts or citations. The
10-case offline adversarial corpus passes 10/10 with zero false support. Five
paid DeepSeek shadow runs are recorded in
`docs/verification/evaluation-results.md`. After bounded retries, exact-sibling
salvage, search fallback and headerless-text handling, the final sample completed
5/5 claim extractions and 5/5 audits with no verification/search errors. The
required 100-story/300-claim human study remains a public release gate.

### [x] E6. Decide whether to annotate one profile

Decision recorded: do not annotate. Technical shadow reliability now passes on
the final five-item sample (4 supported, 2 insufficient, 1 not-checkable, zero
errors), so the internal ledger may collect more data. The blinded
100-story/300-claim review, human citation audit and owner-selected
coverage/cost/latency thresholds remain absent. No public mode, badge or
renderer change was added, and the release gates were not weakened.

---

## Cancelled work — Alibaba model comparison

Cancelled by owner decision on 2026-08-14. Horizon does not use the Alibaba
Token Plan, Qwen workers, or an Alibaba fallback. Production and evaluation use
paid `deepseek-v4-flash` through OpenCode Go. Historical probes are intentionally
removed from the active plan so a future agent cannot mistake them for a route
that should be resumed.

---

## Phase C — per-article pages, site redesign, Elasticsearch search

Owner feedback after live use (2026-08-06): a headline link must open the
article itself, not the middle of a combined page; the site carries too much
non-digest material; the formatting is rejected; the archive must be
searchable by keyword (Elasticsearch was named explicitly).

### [x] C1. One page per article + Telegram links to them

`build_article_pages()` + `publish_site_pages()`; headline href is
`{link_base}/{date}-{lang}/{slug}/` where slug = anchor minus `item-`.
Path-traversal check restored for the issue directory. Tests updated and
added. Committed.

### [x] C2. Site is the digest only

Documentation pages excluded from the published site (`exclude_docs`), nav
reduced to Главная / Дайджесты / Поиск, landing rewritten to two buttons.
Committed.

### [x] C3. Reading-first redesign

`docs/assets/horizon-digest.css` + `article_site_markup()` (site-only
restructure) + `LABELS["ru"]` + `font: false` (Google Fonts link blanked the
page). Verified rendered in a real browser, light scheme, desktop width.
Committed. Dark scheme follows the same custom properties — re-check on the
live site once deployed.

### [x] C4. Elasticsearch live

Code + offline tests (`src/services/search.py`, orchestrator hook,
`scripts/dev_reindex_archive.py`, `deploy/search/`). Deployed 2026-08-07:
ES 8.15.3 + search-api in Docker on the Mac (heap 512 MB, ES localhost-only),
53 articles backfilled, Caddy proxies `/api/search` on the digest domain,
public search verified live. Docker Desktop autoStart enabled so the index
survives reboots.

### [x] C5. Ship it

Committed, bundled to the Mac, pushed to GitHub over SSH (the stored gh
token is dead — `gh auth login` when convenient), site rebuilt and deployed
to `/srv/digest.ninitux.com`, archive republished as per-article pages
(`scripts/dev_republish_archive.py`), a real-headlines Telegram test sent
with links that open the live article pages. The next scheduled run (17:00
MSK) publishes and links natively.

---

## Phase D — cheap pronunciation review

### [ ] D1. Review current narration with DeepSeek Flash and re-narrate

Run the remaining Latin-token backlog through an explicitly configured cheap
model with thinking disabled. Keep the model output as a review report rather
than applying it directly: the first measured run confidently translated
`Help Center` instead of transcribing it. Promote only reviewed readings to the
Tera-only lexicon, regenerate issues 7–10 August, and verify every public audio
object before marking this shipped.
