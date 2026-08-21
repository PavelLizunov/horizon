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
6. **Search & Feeds**: Lunr.js search index, Atom/RSS feeds in English and Russian.
