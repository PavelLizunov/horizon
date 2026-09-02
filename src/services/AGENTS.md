# AGENTS.md — Services Layer Guide (`src/services/`)

## Scope & Hierarchy

- Applies to code under `src/services/`. Inherits root `AGENTS.md` and `src/AGENTS.md` rules.
- Covers delivery services (webhooks, email), search archive indexing, and CLI utility tools (`horizon-webhook`, `horizon-video`).

## Service Architecture & Entry Points

- **Webhook Service (`webhook.py`, `webhook_cli.py`)**:
  - `WebhookNotifier`: Renders and dispatches digest notifications over HTTP GET/POST via `httpx` and `url_security.safe_request`.
  - Supports platforms (`generic`, `feishu`, `lark`, `dingtalk`, `slack`, `discord`) and layouts (`markdown`, `collapsible`). Feishu/Lark uses Card JSON 2.0 with collapsible panels.
  - Delivery modes: `summary`, `summary_and_items`, `headlines`.
  - CLI: `horizon-webhook` (`webhook_cli.py:main`) provides dry-run previews (`--dry-run`), delivery overrides (`--delivery`), and language selection (`--lang`).

- **Email Service (`email.py`)**:
  - `EmailManager`: Handles subscription/unsubscription requests via IMAP (`IMAP4_SSL`) and sends HTML/text digest summaries to subscribers via SMTP (`SMTP_SSL` / `STARTTLS`).
  - Auto-subscribes/unsubscribes on `SUBSCRIBE` / `UNSUBSCRIBE` subject keywords while ignoring `no-reply` senders.

- **Search Indexing (`search.py`)**:
  - `SearchIndexer`: Minimal Elasticsearch writer over `httpx.AsyncClient`. Bulk-indexes (`_bulk`) delivered articles with 1 shard, 0 replicas, and a `russian` stemmer analyzer (`INDEX_BODY`).
  - Document IDs are derived as `{date}-{language}-{slug}` matching MkDocs published site URLs.
  - `build_search_query()` is a test/reference helper and is not called by the deployed proxy. `deploy/search/search_api.py` owns the live read path and additionally uses title highlighting plus safe highlight sentinels; do not assume the two query bodies are identical. Any consolidation is a public search-contract change.

- **Video Sidecar CLI (`video_cli.py`)**:
  - `horizon-video` (`video_cli.py:main`): Runs YouTube extraction ladder (subtitles, ASR, vision fallback) out-of-band to prevent `yt-dlp` or Whisper delays from stalling the main digest pipeline.
  - Forces `mode: "inline"` internally during collection and writes items and statistics to `inbox_file` (`data/video-inbox.json`).

## Technical Invariants & Constraints

1. **Side-Effect & Security Boundaries**:
   - Webhook requests must route through `src/url_security.py` (`validate_http_url`, `safe_request`) to enforce the central SSRF policy; the parent guide records the current DNS-rebinding caveat.
   - Sensitive credentials and secret paths (e.g. Telegram `/bot<token>/` path secrets, secret headers) must be masked using `redact_url()` and `redact_headers()` in log messages, console errors, and dry-run previews.
   - Secrets are loaded dynamically from environment variable names (`url_env`, `password_env`) via `os.getenv()`, never stored directly in configs or models.

2. **Retries & Graceful Degradation**:
   - Webhook notifications catch transport/URL errors (`ConnectError`, `TimeoutException`, `InvalidURL`, `UnsafeURLError`) and return `WebhookDeliveryResult` statuses (`HTTP_FAILURE`, `PLATFORM_FAILURE`, `NETWORK_FAILURE`) rather than raising exceptions that break the orchestrator run.
   - 2xx responses are parsed for platform error payload codes (e.g., Feishu `code != 0`, DingTalk `errcode != 0`, Slack `ok: false`).
   - Email IMAP/SMTP errors and Elasticsearch bulk errors are logged as warnings/errors without crashing pipeline execution.

3. **Webhook, HTML & URL Safety**:
   - Markdown summary outputs are cleaned with `clean_app_summary_markdown()`.
   - HTML tags in Telegram headline messages are escaped with `html.escape()` and restricted to safe tags (`<b>`, `<a href>`).
   - Telegram messages are partitioned by `_TELEGRAM_CHUNK_CHARS` (3900 chars) to stay safely below Telegram's 4096-character API limit.

4. **Search Index & API Coupling**:
   - Index documents (`build_search_documents`) align with published site URL slugs (`{date}-{language}-{slug}`).
   - Schema mapping (`INDEX_BODY`) pins property types (`keyword`, `text`, `float`) and `russian` stemmer behavior.
   - Known gaps: documents store the requested `item.profile` rather than the resolved classification profile; `_bulk` partial failures are logged while `index_documents()` still reports every attempted document as written; and upserts do not prune stale documents for removed pages.

5. **CLI & Environment Compatibility**:
   - Both CLIs use `src/_cli.py` argument helpers and load `.env`. `horizon-webhook` maps `KeyboardInterrupt` to exit 0; `horizon-video` exits 1 for handled configuration/structural errors and otherwise leaves Ctrl-C to normal interpreter semantics.

6. **Offline Testing & Mocks**:
   - All tests in `tests/test_webhook.py`, `tests/test_webhook_cli.py`, `tests/test_email.py`, `tests/test_search.py`, `tests/test_search_api.py`, and `tests/test_video.py` must run offline using `httpx.MockTransport`, `unittest.mock`, or mocked socket/SMTP/IMAP connections.
