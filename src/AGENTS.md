# AGENTS.md — Package Root Guide (`src/`)

## Scope & Hierarchy

- Applies to code under `src/`. Inherits global rules from root `AGENTS.md`.
- Nested `AGENTS.md` files within child packages take precedence for local directory context.
- Keep changes modular, schema-compliant, and verified via offline tests in `tests/`.

## Entry Points & CLI Integration

Entry points registered in `pyproject.toml`:
- `horizon` -> `src/main.py:main` (Main CLI pipeline runner)
- `horizon-mcp` -> `src/mcp/server.py:main` (Model Context Protocol stdio server)
- `horizon-wizard` -> `src/setup/wizard.py:main` (Interactive setup wizard)
- `horizon-webhook` -> `src/services/webhook_cli.py:main` (Webhook test CLI utility)
- `horizon-video` -> `src/services/video_cli.py:main` (Video sidecar CLI utility)

Shared top-level CLI & logging modules:
- `src/_cli.py`: Shared argument helpers (`add_data_dir_arguments`, `add_log_level_argument`).
- `src/logging_config.py`: Rich console logging router (`configure_logging`).
- `src/console_icons.py`: Terminal icon styles (`get_icons`: `emoji`, `nerd`, `ascii`).

## System Layering & Key Modules

1. **Core Models (`src/models.py`)**:
   - Single source of truth for Pydantic models (`Config`, `SourcesConfig`, `ContentItem`, etc.) and `SourceType` enum.
   - Defines `SOURCE_REGISTRY` mapping source types to configuration definitions.
   - **Rule**: Schema edits in `models.py` must stay backward-compatible and synchronized with `data/config.example.json`.

2. **Pipeline Orchestration (`src/orchestrator.py`)**:
   - Central coordinator (`HorizonOrchestrator`) connecting scrapers, AI analysis/enrichment, Evidence Ledger verification, deduplication, search indexing, and delivery services.
   - **Rule**: Scraper, AI, or verification interface changes directly couple with `orchestrator.py`. Ensure pipeline flow wiring matches module contracts.

3. **Security & Utility Layer**:
   - `src/url_security.py`: Public-address URL validation (`validate_public_http_url`, `resolve_public_http_url`) and address-pinned requests (`safe_request`). Every initial/redirect destination is resolved once, connected by validated IP, and sent with the original Host header and TLS SNI.
   - `src/_file_utils.py`: Atomic file writing (`_atomic_write_text`, `_atomic_write_bytes`) via temporary file replacements.

## Child Packages

Defer package-specific implementation details to child guides or module documentation:
- `src/ai/`: Provider clients (`client.py`), analysis (`analyzer.py`), enrichment (`enricher.py`), summarization (`summarizer.py`), classification (`classifier.py`), narration preparation (`narration.py`), and prompts (`prompting/`).
- `src/extractors/`: Full text extraction engines (`trafilatura.py`, `base.py`, `registry.py`).
- `src/mcp/`: Model Context Protocol server (`server.py`), tools (`service.py`), and adapter (`horizon_adapter.py`). See `src/mcp/README.md`.
- `src/processing/`: Profile engine (`profiles.py`), deduplication keys, search tools (`tools.py`), and content data models (`content.py`).
- `src/scrapers/`: Scrapers per source (`base.py`, `rss.py`, `video.py`, `fourpda.py`, `github.py`, `reddit.py`, etc.).
- `src/services/`: External delivery services (`webhook.py`, `email.py`), search indexing (`search.py`), and CLI entry modules (`webhook_cli.py`, `video_cli.py`).
- `src/setup/`: Interactive setup wizard (`wizard.py`), configuration presets (`presets.py`), and tag aliases (`tag_aliases.py`).
- `src/storage/`: Configuration loading and state persistence (`StorageManager` in `storage/manager.py`).
- `src/verification/`: Evidence Ledger fact-checking engine (`claims.py`, `evidence.py`, `ledger.py`, `evaluation.py`, `audit.py`).

## Core Invariants & Integration Rules

1. **Public Compatibility**:
   - `models.py` schema is the contract. Adding or updating a source requires sync across `models.py` -> `SOURCE_REGISTRY` -> `src/scrapers/` -> `src/orchestrator.py` -> `data/config.example.json` -> `tests/`.
   - Entry point callables and CLI arguments in `_cli.py` and `main.py` must maintain public interface stability.

2. **URL Security**:
   - Web queries and link fetches must route through `src/url_security.py` as the central address-pinned SSRF policy; never validate a hostname and then issue an independently resolved request.

3. **Graceful Degradation**:
   - External fetch, scrape, or AI failures are isolated per source. One failed source must not abort the run; an all-sources fetch failure remains a fatal pipeline condition.
   - Verification gracefully handles search rate limits and errors without rendering scary internal error statuses to public outputs.

4. **Offline Testing**:
   - All tests in `tests/` must run offline without live API keys or external network connections. Heavy/platform dependencies (e.g. `yt-dlp`, `mlx-whisper`) must be imported lazily or mocked in test contexts.
