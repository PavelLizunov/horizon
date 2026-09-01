# AGENTS.md — Test Suite Guide

This directory contains the `pytest` test suite for Horizon.

## Local Invariants
- **100% Offline & Secret-Free**: Tests must run without network access, external services, or real API keys. All credentials use environment variable placeholders (e.g., `api_key_env`).
- **Deterministic Mocks**: External APIs (OpenAI, DashScope, DuckDuckGo, 4PDA, YouTube, Telegram) and IO operations must be deterministically mocked using `unittest.mock.patch`, pytest fixtures, or synthetic response objects.
- **No Unsanctioned Test Edits**: When fixing bugs or refactoring, do NOT edit or relax existing test assertions to make failing tests pass. Update tests only when functional requirements or API contracts explicitly change.

## Test Commands
```bash
.venv/bin/pytest                          # Run full test suite
.venv/bin/pytest tests/test_video.py -q   # Run specific test module
```

## Representative Component Test Mapping

The table names high-signal suites, not an exhaustive manifest; discover the current set with `glob`/`pytest --collect-only`.

| Component | Source Path (`src/`) | Representative Test Files (`tests/`) |
|---|---|---|
| **Scrapers & Ingestion** | `src/scrapers/` | `test_fourpda.py`, `test_video.py`, `test_rss.py`, `test_reddit.py`, `test_twitter.py`, `test_gdelt.py`, `test_google_news.py`, `test_openbb_scraper.py`, `test_extractors_registry.py`, `test_extractors_trafilatura.py`, `test_fetch_reporting.py` |
| **AI & LLM Services** | `src/ai/` | `test_analyzer.py`, `test_classifier.py`, `test_enricher.py`, `test_summarizer.py`, `test_narration.py`, `test_prompting.py`, `test_azure_client.py`, `test_minimax_client.py`, `test_chained_client.py` |
| **Processing, Storage & Search** | `src/processing/`, `src/storage/`, `src/services/search.py`, `src/url_security.py` | `test_profiles.py`, `test_category_thresholds.py`, `test_category_wiring.py`, `test_cross_source_duplicates.py`, `test_content_selection.py`, `test_balanced_digest.py`, `test_search.py`, `test_storage.py`, `test_url_security.py` |
| **Evidence Ledger & Verification** | `src/verification/` | `test_verification_claims.py`, `test_verification_discovery.py`, `test_verification_evidence.py`, `test_verification_ledger.py`, `test_verification_audit.py`, `test_verification_status.py`, `test_verification_incidents.py`, `test_verification_evaluation.py` |
| **Delivery Services** | `src/services/` | `test_telegram.py`, `test_email.py`, `test_webhook.py`, `test_webhook_cli.py` |
| **MCP Integration** | `src/mcp/` | `test_mcp_server.py`, `test_mcp_adapter.py`, `test_mcp_run_store.py`, `test_mcp_errors.py`, `test_mcp_service_smoke.py` |
| **CLI & Orchestrator** | `src/_cli.py`, `src/main.py`, `src/orchestrator.py`, `deploy/` | `test_main.py`, `test_cli.py`, `test_branding.py`, `test_console_icons.py`, `test_collection_status.py`, `test_daily_deploy.py`, `test_logging_config.py`, `test_setup_wizard.py` |

## Regression Testing Standards
- **API & Schema Changes**: Any change to Pydantic models (`src/models.py`) or API output schemas requires updating/adding corresponding validation tests.
- **Bug Fixes**: Every bug fix MUST include a dedicated regression test reproducing the issue and asserting the correct behavior.
- **Performance & Resource Constraints**: Performance-sensitive routines (e.g. ASR Metal buffer cleanup, deduplication filtering, or claim budgets) need deterministic regression tests for disposal, bounded work, and output size; avoid flaky wall-clock assertions.

## Fixtures & Test Data
- Shared test datasets reside in `tests/fixtures/` (see `tests/fixtures/AGENTS.md`).
- Configuration and path setup is handled by `tests/conftest.py`.

## Inheritance
Inherits from root `AGENTS.md`.
