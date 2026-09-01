# Site Publishing Specification

## 1. Objective
Render daily AI news digest into an accessible, responsive, searchable static web portal using Material for MkDocs, deployed automatically to a public ingress.

---

## 2. Structure & Pages
1. **Homepage (`/`)**: Overview, calendar navigation, issue archives, search.
2. **Daily Issue Pages (`/digest/YYYY-MM-DD-lang/`)**: Summary index for the day.
3. **Article Pages (`/digest/YYYY-MM-DD-lang/<category>-<n>/`)**: Full enriched article, source links, Evidence Ledger corroboration badge, and embedded audio player.
4. **Collection Scope Page (`/collection/`)**: Dynamic, live listing of all configured sources, categories, thresholds, and last-run ingestion metrics (`docs/collection.md`).
5. **Checks Page (`/checks/`)**: Overview of factual corroboration health and verification coverage (`docs/checks.md`).
6. **Archive Search (`/search/`)**: The browser queries a read-only Elasticsearch proxy through `GET /api/search?q=…`; `GET /search?q=…` is an equivalent direct alias. The successful response contract is `{"total": <int>, "hits": [...]}` with at most 30 hits. Backend failures return HTTP 502 with `{"total": 0, "hits": [], "error": "Search backend unavailable", "error_code": "backend_unavailable"}` and are never cached.
7. **Static Search & Feeds**: Generated digest directories are excluded from MkDocs/Lunr indexing. The current deployment does not publish the legacy Atom/RSS feed artifacts.
