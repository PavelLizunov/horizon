# Site Publishing Architecture Plan

## 1. Build Pipeline
1. `DailySummarizer.build_article_pages()` generates individual Markdown documents for every selected item under `docs/digest/YYYY-MM-DD-lang/`.
2. `scripts/dev_collection_status.py --write-site docs/collection.md` compiles active configuration and latest run statistics into `docs/collection.md`.
3. `StorageManager.write_site_index()` updates root issue listing and navigation.
4. `mkdocs build` compiles Markdown into static HTML/CSS/JS.
5. Ingress sync: `deploy/run-daily.sh` tar-streams build output to web ingress via SSH/rsync.

## 2. Invariants
* Secrets, raw credentials, and sensitive query tokens are never included in generated public pages.
* Clean, semantic HTML structure with high-contrast accessibility and mobile touch targets.
