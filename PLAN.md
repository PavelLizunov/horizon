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

## Phase B — DeepSeek A/B

Goal: decide with evidence whether to move Horizon's LLM work from
`qwen3.8-max-preview` to DeepSeek. Not a migration — a measurement.

### [x] B0. Establish what is actually available — measured 2026-08-06

**DeepSeek is on the existing Alibaba Token Plan endpoint.** Queried
`GET /compatible-mode/v1/models` against
`token-plan.ap-southeast-1.maas.aliyuncs.com` with the existing
`DASHSCOPE_API_KEY`: 11 models, including **`deepseek-v4-flash-0731`** and
**`deepseek-v4-pro`**.

This collapses the whole "migration" into a one-line config change —
`ai.model`. Same provider (`ali`), same `base_url`, same key, same quota. No new
billing relationship, no new provider class, no `provider_chain` work.

Both probes returned normally (13 512 prompt / 2 output, then 24 / 2 001), so
the model works through the existing client with no code changes.

Also observed: **`qwen3.8-max-preview` is not in the model list** — only
`qwen3.8-max`. The live config names the retired preview and is silently
rerouted, which matches the known 2026-08-03 retirement.

Fixed here: `AI_PROVIDER_DEFAULTS` (`src/models.py`) defaulted the *direct*
DeepSeek API to `deepseek-chat`, retired 2026-07-24 and no longer routed
anywhere. Now `deepseek-v4-flash`.

**Blocked: the credit coefficient is unmeasured.** The comparison that matters
is credits per token on the Token Plan, not dollars — Alibaba does not publish
per-model coefficients. The existing measurement tool (`~/.qquota`, which
produced the qwen figures of 612 credits/1M input and ~1 700 output) currently
fails: an SSL handshake timeout, then `KeyError: 'per5HourPercentage'` from
Alibaba's console usage API, whose response shape appears to have changed.
Until that is repaired or the numbers are read from the console by hand, the
**cost half of the A/B cannot be completed**. The quality half is not blocked.

DeepSeek's own public pricing (V4-Flash, $0.14/1M in, $0.28/1M out ≈ $0.053 per
reference run) is *not* the relevant number while the traffic goes through the
Token Plan quota. Keep it only as an upper bound if the direct API is ever used.

### [x] B1. Capture a replayable item set — `scripts/dev_capture_items.py`

Both models must score the *same* items, or the comparison is worthless — a
different day is different news. Fetch once, serialize `ContentItem`s to JSON,
replay.

Reuse the sidecar's proven round-trip: `write_inbox` /
`ContentItem.model_validate` in `src/scrapers/video.py` already demonstrate that
`model_dump(mode="json")` survives a disk round-trip. A dev script in
`scripts/` following the `dev_check_*.py` convention.

### [ ] B2. Run both models over the captured set

Analysis + enrichment under each provider, outputs written side by side.
`provider_chain` is a *failover* chain, not per-stage routing, so this means two
runs with different `ai.provider`, not one clever config.

**This costs real money on both sides.** Budget it, cap the item count (10–15 is
plenty), and get the owner's go before running.

### [ ] B3. Grade on the criteria that actually matter

Not vibes. The manual audit already established what separates good from bad
here:

1. **Faithfulness** — every specific claim traceable to the source text. Method
   used before: extract concrete assertions from the digest, grep the source
   description/transcript for each. qwen scored 5/5 on the reference item.
2. **Calibrated scepticism** — does the fact-check block flag an unsupported
   claim, or parrot it? qwen correctly flagged "«думай пошагово» ухудшает
   половину топовых моделей" as unverifiable.
3. **De-clickbaiting** — is a sensational title rewritten into a descriptive one?
4. **Language discipline** — CJK leakage into Russian output. qwen leaks ~8×
   per run and the retry now reports persistent leaks
   (`Language leak persists after retry`). DeepSeek is also a Chinese model, so
   measure this, do not assume it is better.
5. **Cost per run** — from `record_usage`.

The grader must not be the model being graded. Score blind where practical.

### [ ] B4. Decide and record

Whichever way it goes, write the numbers into `CHANGELOG.md` and
`docs/configuration.md` so the next agent does not redo the experiment. A
negative result is a result.

**Standing caveat on the cost argument:** the digest is ~2.6 % of the weekly
Alibaba quota (292 credits/run, ~146 inside the 17:00 MSK off-peak window,
against 40 000/week). Moving it off qwen frees 2.6 % of a quota that interactive
work already overruns several-fold. The case for switching should rest on
quality-per-dollar or on freeing the quota entirely, not on the digest's own
cost — that is small either way.

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
