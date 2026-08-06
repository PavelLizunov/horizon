# Telegram Delivery

Horizon sends **headlines** to Telegram, deep-linked into the published digest
site. The full digest is not sendable and never will be — see the limits below.

## Why headlines and not the digest

Measured on a real digest: **38 461 characters**, 11–50 items, items ranging
1 555–5 408 characters each. Telegram's `sendMessage` cap is 4 096 characters,
so a full digest is roughly ten messages before any formatting is considered.

Worse, Telegram's HTML parse mode accepts a short closed list of tags:

```
b/strong  i/em  u/ins  s/strike/del  a  code  pre
span.tg-spoiler  tg-spoiler  tg-emoji  blockquote  blockquote expandable
```

The digest contains `<details>`, `<summary>`, `<ul>`, `<li>`, ATX headings and
`<a id>` — **none** of which are on that list. An unsupported tag does not
degrade: Telegram answers `Bad Request: can't parse entities` and **rejects the
whole message**. There is no partial delivery.

`blockquote expandable` (Bot API 7.4) is the native collapsible primitive and
was considered for per-item messages. It was dropped once the site existed:
headlines plus a link are one message instead of twelve, with one notification
instead of twelve.

## Configuration

```json
"webhook": {
  "enabled": true,
  "url_env": "TELEGRAM_WEBHOOK_URL",
  "platform": "generic",
  "delivery": "headlines",
  "link_base": "https://digest.example.com",
  "request_body": {
    "chat_id": "-1001234567890",
    "parse_mode": "HTML",
    "disable_web_page_preview": true,
    "text": "#{headlines}"
  }
}
```

| Field | Why |
|-------|-----|
| `platform: "generic"` | Telegram needs no platform of its own — `generic` already recognises its `{"ok": false}` error shape. |
| `delivery: "headlines"` | The axis that controls how many messages and what is in each. |
| `link_base` | Base of the published site. Links become `{link_base}/{date}-{lang}/#{anchor}`. **Unset**, links fall back to each item's source URL, so this works before the site exists. |
| `disable_web_page_preview` | Not optional. Without it Telegram renders a preview card for the first link and the message becomes a wall. |
| `request_body` as an **object** | Must be a JSON object, not a JSON string. Substitution into raw JSON text breaks on newlines. |

### The token

Put it in `.env` and reference the variable **name** from config:

```bash
TELEGRAM_WEBHOOK_URL=https://api.telegram.org/bot<TOKEN>/sendMessage
```

Never write `${TELEGRAM_TOKEN}` inside `request_body`. Config-wide `${VAR}`
expansion happens at load time (`_expand_env_vars`) and `save_config` writes the
model back, so running `horizon-wizard` afterwards would bake the secret onto
disk. `url_env` is read at send time and never persisted.

The token lives in the URL *path*, so `redact_url` strips it there specifically
— query-and-fragment redaction is not enough for Telegram.

`chat_id` for a channel starts with `-100`. Find it by messaging the bot and
reading `https://api.telegram.org/bot<TOKEN>/getUpdates`.

## What the payload looks like

Built from `DailySummarizer.build_view()`, never from the rendered markdown —
that is what makes the unsupported tags structurally impossible rather than
merely filtered:

```html
<b>Технологии</b>
1. <a href="https://digest.example.com/2026-08-06-ru/#item-tech-news-1">Заголовок</a> 8.0/10
2. <a href="https://digest.example.com/2026-08-06-ru/#item-tech-news-2">Другой</a> 7.0/10
```

Only `<b>` and `<a href>`. A test asserts the tag set of a built payload is a
subset of `{b, a}`; that test is what turns "message silently rejected" into a
red CI line.

Titles are escaped with `html.escape`. This is load-bearing, not defensive:
titles are model output over scraped content, so one literal `<` would cost the
whole day's digest. Titles are also capped at 200 characters so a single
pathological item cannot produce a line no chunk can hold.

## Chunking

Lines are packed into chunks of **≤ 3 900 characters**. Measured: a 30-item
digest renders to 4 660 characters of headlines — already over the cap — and
`digest.max_items` allows 50. In practice 30 items → 2 messages, 50 → 3.

The budget is deliberately conservative. Telegram documents its limit as 4 096
"after entities parsing", which would exclude `<a href>` markup from the count,
but an over-limit message is *rejected*: being wrong conservatively costs one
extra message, being wrong the other way costs the day.

## Rate limits

Roughly 20 messages per minute to one group, about one per second per chat, 30
per second globally, with per-method buckets. Exceeding them returns HTTP 429
with `retry_after`.

Two or three messages a day sit far below all of these, which is why **no retry
or backoff logic exists**. A failed day self-heals the next day. If delivery
ever becomes chattier, that assumption needs revisiting.

## Verifying without sending

```bash
horizon-webhook --dry-run
```

Prints the fully rendered request with the URL and headers redacted. Check two
things by eye: no tag other than `<b>` and `<a>`, and no token in the output.
