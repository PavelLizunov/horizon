# Site Publishing Tasks & Implementation Checklist

- [x] Configure MkDocs Material theme, typography, and custom CSS/JS assets.
- [x] Implement multi-page per-article rendering in `src/ai/summarizer.py`.
- [x] Implement dynamic collection status page generator (`scripts/dev_collection_status.py`).
- [x] Implement the Elasticsearch archive indexer and browser search page.
- [x] Exclude legacy feed artifacts and generated digest directories from MkDocs/Lunr indexing.
- [x] Harden the public search proxy with sanitized errors, success-only caching, bounded concurrency, and request timeouts.
- [x] Add offline HTTP/cache/concurrency regression coverage and update the owning API documentation.
- [x] Implement ingress shipping script (`deploy/run-daily.sh`).
- [x] Sanitize error states and dollar estimates from published article views.
