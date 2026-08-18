# Sources Architecture Plan

## 1. Component Boundaries
* All scrapers inherit from `src/scrapers/base.py:BaseScraper`.
* Shared `httpx.AsyncClient` passed down from `HorizonOrchestrator.fetch_all_sources()`.
* Each scraper returns `list[ContentItem]`, where:
  * `id`: `{source}:{subtype}:{native_id}` format.
  * `source_type`: enum `SourceType`.
  * `url`: canonical direct link or deep post link.
  * `published_at`: normalized UTC timestamp.
  * `metadata`: dictionary with profile routing, category tags, and source-specific context.

## 2. Ingestion Error Handling
* `orchestrator._fetch_with_progress()` catches per-source exceptions.
* Pipeline proceeds if at least one source succeeds.
* Individual scraper degradation is recorded in `FetchReport`.
