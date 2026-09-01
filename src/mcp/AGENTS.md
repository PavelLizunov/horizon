# AGENTS.md — MCP Package Guide (`src/mcp/`)

This package provides a Model Context Protocol (MCP) server exposing the Horizon pipeline as staged tools and read-only resources over stdio.

## Scope & Hierarchy

- Applies to all code and documentation under `src/mcp/`.
- Inherits global rules from root `AGENTS.md` and `src/AGENTS.md`.
- Keep rules concise and local to MCP component invariants; do not duplicate parent rules.

## Component Architecture

- `server.py`: FastMCP server instance, CLI entry point (`horizon-mcp`), in-memory metrics collector, tool/resource handler decorators, stdio event loop.
- `service.py`: `HorizonPipelineService`, high-level pipeline stage coordinator, context builder, config secret redaction (`_redact_config`).
- `horizon_adapter.py`: Dynamic Horizon runtime loader (`load_runtime`), repo/config path resolution, source filtering, Pydantic `ContentItem` serialization/deserialization.
- `run_store.py`: `RunStore` intermediate artifact persistence under `data/mcp-runs/<run_id>/`, downstream stage invalidation, monotonic microsecond timestamping, path security checks.
- `errors.py`: `HorizonMcpError` dataclass with stable error codes (`code`, `message`, `details`).

## Public API Stability Contracts

### Tools (13 Public Tools)
Tool names, parameters, and JSON response envelopes (`ok`, `tool`, `data`/`error`, `meta`) are public API:
- Configuration: `hz_validate_config`
- Pipeline Execution: `hz_fetch_items`, `hz_score_items`, `hz_filter_items`, `hz_enrich_items`, `hz_generate_summary`, `hz_run_pipeline`
- Artifact Inspection: `hz_list_runs`, `hz_get_run_meta`, `hz_get_run_stage`, `hz_get_run_summary`
- Server & Delivery: `hz_get_metrics`, `hz_send_webhook`

### Resources (7 Public Resources)
- `horizon://server/info`
- `horizon://metrics`
- `horizon://runs`
- `horizon://runs/{run_id}/meta`
- `horizon://runs/{run_id}/items/{stage}`
- `horizon://runs/{run_id}/summary/{language}`
- `horizon://config/effective`

### Artifact Stages & File Contracts
Stage names and file mappings inside `data/mcp-runs/<run_id>/` are public contracts:
- `raw` -> `raw_items.json`
- `scored` -> `scored_items.json`
- `filtered` -> `filtered_items.json`
- `enriched` -> `enriched_items.json`
- Summary outputs -> `summary-<language>.md`
- Metadata -> `meta.json`

## Key Invariants & System Rules

1. **Stdio Stdout Purity**:
   - Stdout is strictly reserved for JSON-RPC MCP framing.
   - All logging, progress updates, rich console outputs, and errors MUST be routed to stderr via `Console(stderr=True)` and `configure_logging(console)`. Never call standard `print()` or write to stdout.

2. **Native Business Logic Reuse**:
   - The MCP layer MUST NOT reimplement scraping, scoring, filtering, enrichment, or summarization business logic.
   - Always delegate directly to core modules: `HorizonOrchestrator`, `StorageManager`, `DailySummarizer`, `ContentAnalyzer`, `ContentEnricher`, and `src/models.py`.

3. **Run-Store & Path Security**:
   - Validate `run_id` using `RUN_ID_RE` (`^[A-Za-z0-9][A-Za-z0-9._-]*$`) and verify resolved path relative to `runs_root` to prevent directory traversal.
   - Validate summary language strings using `LANGUAGE_RE`.
   - File updates MUST use atomic file replacement (`_atomic_write_text`).
   - ISO timestamps must maintain microsecond precision (`timespec="microseconds"`) and monotonic increments for string-based sorting in `list_runs()`.
   - Saving or modifying an upstream stage MUST invalidate all downstream stage files, summaries, and associated stage metadata.
   - Known gaps: metadata updates and stage invalidation are multi-step read/modify/write operations without inter-process locking, and `list_runs(limit)` reads/sorts every run's metadata before applying the limit. Atomic replacement prevents torn files but not lost concurrent updates.

4. **Error Translation & Handling**:
   - Application errors must raise or translate into `HorizonMcpError` carrying structured codes (e.g. `HZ_RUN_NOT_FOUND`, `HZ_STAGE_NOT_FOUND`, `HZ_CONFIG_NOT_FOUND`, `HZ_INVALID_INPUT`, `HZ_INVALID_STAGE`).
   - `server.py` wraps tool execution in standard envelopes (`_ok` / `_err`) and records call duration and error telemetry.

5. **Secret Sanitization**:
   - Config outputs in tools and resources MUST pass through `_redact_config()` before returning JSON. It redacts expanded secret values while deliberately preserving non-secret `*_env` variable names as configuration references.
   - Secrets loaded via `.env` or `mcp.secrets.json` populate environment variables without logging key values.

6. **Doc & Test Synchronization**:
   - Any modifications to tools, resources, stage formats, or error codes MUST be kept in sync across `src/mcp/server.py`, `src/mcp/service.py`, `src/mcp/README.md`, `src/mcp/integration.md`, and `tests/test_mcp_*.py`.

## Verification

Before finalizing work under `src/mcp/`:
- Run offline MCP pytest suite: `./.venv/bin/pytest tests/test_mcp_*.py`
- Verify git formatting and whitespace: `git diff --check -- src/mcp/AGENTS.md`
