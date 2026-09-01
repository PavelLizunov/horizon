# AGENTS.md — Extractors Package (`src/extractors/`)

## Scope & Purpose

This package provides full-article text extraction engines and an extractor registry.

## Registry & API Contracts

- **`BaseExtractor`** (`src/extractors/base.py`):
  Abstract base interface:
  `async def extract(self, url: str, client: httpx.AsyncClient) -> Optional[str]`
  Returns extracted plain text string or `None` on failure.

- **`TrafilaturaExtractor`** (`src/extractors/trafilatura.py`):
  Concrete implementation using the `trafilatura` library.
  Fetches HTML via `src.url_security.safe_request(client, "GET", url, headers=ARTICLE_HEADERS)` to enforce SSRF safety.
  Parses content using `trafilatura.extract(html, favor_precision=..., favor_recall=...)` based on `TrafilaturaExtractorConfig`.

- **`ExtractorRegistry`** (`src/extractors/registry.py`):
  Maps extractor names to initialized `BaseExtractor` instances.
  Defaults: `ExtractorType.TRAFILATURA` maps to `TrafilaturaExtractorConfig()`.
  Custom configuration dictionary overrides or additions are passed on instantiation `ExtractorRegistry(config)`.
  `get(name: str) -> Optional[BaseExtractor]` retrieves an extractor instance by name.

## Lazy Dependency Boundary & Failure Degradation

- **Dependency Boundary**: `trafilatura` is a standard project dependency but is imported lazily inside `extract()`. A partial/minimal installation without it logs a warning and returns `None` instead of failing package import.
- **External & Parsing Failure Handling**:
  - Network errors or HTTP status failures (`httpx.HTTPError`, `UnsafeURLError`) log warnings and return `None`.
  - Trafilatura extraction exceptions (`Exception`) or empty extraction results log warnings and return `None`.
- **Invariant**: Extraction operations degrade gracefully and never raise exceptions to break pipeline execution.

## Verification & Exact Tests

Run offline tests covering extractors:
- `.venv/bin/pytest tests/test_extractors_registry.py -q`: Tests default registration, user configuration overrides, custom named extractor entries, and unknown key lookups (`None`).
- `.venv/bin/pytest tests/test_extractors_trafilatura.py -q`: Tests text extraction, empty result fallback, HTTP status errors, extraction exception handling, and missing dependency handling.
