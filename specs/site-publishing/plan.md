# Site Publishing Architecture Plan

## 1. Build Pipeline
1. `DailySummarizer.build_article_pages()` generates individual Markdown documents for every selected item under `docs/digest/YYYY-MM-DD-lang/`.
2. `scripts/dev_collection_status.py --write-site docs/collection.md` compiles active configuration and latest run statistics into `docs/collection.md`.
3. `StorageManager.write_site_index()` updates root issue listing and navigation.
4. `mkdocs build` compiles Markdown into static HTML/CSS/JS.
5. Ingress sync: `deploy/run-daily.sh` tar-streams build output to web ingress via SSH/rsync.

## 2. Archive Search
1. `SearchIndexer` upserts published article documents into the private Elasticsearch index; index failure degrades the run without blocking site publishing.
2. `docs/search.md` calls the same-origin `/api/search?q=…` route. Reverse proxy forwards only that route to `deploy/search/search_api.py`; Elasticsearch remains bound to localhost.
3. The stdlib proxy shapes fixed-size, read-only queries and retains the existing successful response fields. It sanitizes backend failures as `backend_unavailable`, caches only 2xx responses, and applies `no-store` to every non-2xx response.
4. `SearchHTTPServer` bounds active handler threads with `SEARCH_MAX_CONCURRENCY` and applies `SEARCH_REQUEST_TIMEOUT` to client socket I/O and Elasticsearch requests.
5. `tests/test_search_api.py` verifies aliases, request normalization, response/cache contracts, sanitized failures, concurrency bounds, and slow-client release entirely offline.

## 3. Invariants
* Secrets, raw credentials, sensitive query tokens, internal backend URLs, and exception details are never included in generated pages or public API responses.
* Clean, semantic HTML structure with high-contrast accessibility and mobile touch targets.
* Search API compatibility is additive: successful envelopes and both endpoint aliases remain stable.
