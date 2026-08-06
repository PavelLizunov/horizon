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

### [ ] A4. MkDocs configuration

`mkdocs.yml` at repo root: material theme, `language: ru`, light/dark palette,
`pymdownx.details`, `toc` with `permalink`, explicit `nav`, `not_in_nav: digest/*`.

**Do not delete the Jekyll files** — `docs/_config.yml`, `_includes/`,
`feed-*.xml`, `assets/js/horizon.js`, `assets/css/horizon.css` are upstream's;
deleting them buys a merge conflict forever. Use `exclude_docs` (MkDocs 1.5+,
gitignore syntax).

Two files must change anyway: `docs/index.md` (Liquid loops render as literal
text and it is the site root, so it cannot be excluded) and
`.github/workflows/deploy-docs.yml` (trigger → `workflow_dispatch`).

**Turning off GitHub Pages is a manual repo-settings step** — otherwise the
`gh-pages` branch keeps serving the stale Cayman site.

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

### [ ] A5. Telegram headline delivery

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

### [ ] A6. Documentation

`data/config.example.json` (loaded by `tests/test_mcp_service_smoke.py:66`),
`docs/configuration.md`, `README.md`, `CHANGELOG.md`, and a new
`docs/telegram-delivery.md` recording the measured limits so nobody re-researches
them.

Note for the Telegram setup section: use `url_env`, **never**
`${TELEGRAM_TOKEN}` inside `request_body` — `_expand_env_vars`
(`src/storage/manager.py:30-54`) expands at load and `save_config` (`:102`)
writes the model back, so running `horizon-wizard` would bake the secret to disk.

### [ ] A7. Infrastructure (needs owner access, not code)

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

**First, a real bug regardless of the outcome:** `AI_PROVIDER_DEFAULTS`
(`src/models.py:176`) still defaults DeepSeek to `deepseek-chat`, which was
**retired on 2026-07-24** — calls are no longer routed anywhere. Current models
are `deepseek-v4-flash` and `deepseek-v4-pro`. Fix the default and note it in
`CHANGELOG.md`.

Cost context, from the measured reference run (137 669 in / 122 273 out):
V4-Flash at $0.14/1M input and $0.28/1M output ≈ **$0.053 per run**, ~$1.6/month.
Verify current pricing before committing to it — this figure came from search
results, not the vendor's own page.

### [ ] B1. Capture a replayable item set

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
