# AGENTS.md — Storage Package (`src/storage/`)

## Scope & Purpose

This package manages configuration loading, environment variable expansion, state persistence, subscriber state, and site page publishing (`StorageManager` in `src/storage/manager.py`).

## Filesystem Atomicity & Path Safety

- **Atomic Writes**: Text and byte writes use `_atomic_write_text` / `_atomic_write_bytes` from `src._file_utils`. Writes occur via a same-directory temporary `.tmp` file replaced atomically using `os.replace`. If an error occurs, the existing destination file remains unchanged and temp files are cleaned up.
- **Path Traversal Safety**: `safe_output_path(root, filename)` currently permits only a direct child of `root`; absolute paths, traversal, and nested filenames all raise `ValueError`. Treat that flat-output restriction as part of the current API until a tested contract change says otherwise.

## Configuration & Environment Expansion

- **Configuration Loading (`load_config`)**: Reads JSON from `config_path` (default `data/config.json`) and parses it into `Config` Pydantic models (`src/models.py`).
- **Environment Expansion (`_expand_env_vars`)**: Recursively resolves `${VAR}` references across strings, dictionaries, and lists. Unset environment variables remain as literal placeholders (`${MISSING}`) to fail visibly downstream rather than failing silently.
- **Config Persistence (`save_config`)**: Writes config JSON atomically, creating an optional `.json.bak` backup.

## Site Output, Deep-Links & Digest Responsibilities

- **Repository Site Root (`SITE_DIGEST_DIR`)**: Anchored to `_REPO_ROOT / "docs" / "digest"` (`Path(__file__).resolve().parents[2]`), ensuring launchd or cron runs write into the repository site tree regardless of working directory. The generated article pages are gitignored; only the placeholder index and local guide are tracked.
- **Deep-Link Coupling (`publish_site_pages`)**: Publishes each article as an individual markdown page (`docs/digest/{date}-{language}/{page.slug}.md`). Granular URLs enable external delivery (e.g. Telegram) to deep-link to specific published articles.
- **Front Matter & Search Index Exclusion**: Prepends YAML front matter (`search:\n  exclude: true`) to exclude digest pages from `search_index.json` bloat, and injects explicit JSON-escaped titles (`title: ...`) so MkDocs renders proper browser tab and preview titles.
- **Site Index Regeneration (`write_site_index`)**: Rebuilds `docs/digest/index.md` listing recent digest issues with date and article count (`hz-archive`). Needed because git operations on deployed boxes can restore the placeholder over the generated archive listing.

## Verification & Exact Tests

Run offline tests covering storage:
- `.venv/bin/pytest tests/test_storage.py -q`: Tests configuration loading errors (missing file, invalid JSON, Pydantic validation failure), recursive `${VAR}` env expansion, custom config paths, path escape rejection in summaries and site pages, atomic file replacement error recovery, search-exclusion front matter, explicit page titles, site index regeneration (newest-first ordering and article counts), and subscriber email list operations.
