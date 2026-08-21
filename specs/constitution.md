# Horizon Project Constitution

## 1. Core Principles & Philosophy

1. **Spec-Driven Development (SDD)**: Specifications, technical plans, and granular task lists under `specs/` are the executable source of truth. Features are designed and verified against specifications before implementation.
2. **Measurement Over Assertion**: Performance, memory, token usage, and model accuracy must be measured with concrete tools (`mx.get_active_memory()`, token usage snapshots, diff evaluations), never asserted or assumed.
3. **Graceful Degradation**: External failures (network blocks, API timeouts, missing subtitles, search rate limits) must reduce data volume or detail, never crash the pipeline or produce a 500/broken run.
4. **Honest Public Presentation**: Publicly published artifacts and web pages must present only verified, clean facts. Internal error states (`verification_error`, `check_error`, `not_checked`) and raw financial token estimations are stripped from public readers.
5. **Strict Secret Isolation**: No API keys, credentials, or cookies are ever committed, logged, or exposed in public pages. Configuration stores only variable names (`api_key_env`), loaded via `.env`.

---

## 2. Architectural Invariants

### 2.1 Testing Discipline
* **All tests run offline**: The `pytest` test suite must pass completely with network access disabled and without API keys.
* External services, LLM calls, and network requests must be mocked with deterministic fixtures.
* Every new scraper, processing rule, and UI renderer must ship with full offline unit tests in `tests/`.

### 2.2 Token & Model Cost Discipline
* LLM calls cost real money. Output volume dominates the bill (~71% on standard tariffs).
* Never run full `horizon` pipeline commands to "check that code works". Use `pytest` and offline/dry-run scripts in `scripts/`.
* Cost control levers: raise category thresholds, reduce `digest.max_items`, or prune optional enrichment blocks.

### 2.3 Evaluator Segregation
* **Never let a model grade its own generation**:
  * Voice generation (TeraTTSv2) is graded by a distinct ASR model (Whisper).
  * Article enrichment is verified by an independent search and evidence evaluator.
  * Pronunciation review uses a separate dedicated lightweight model (`ai.pronunciation_model`), never inheriting the generation model.

### 2.4 Speech & Publishing Decoupling
* Text publishes first: `deploy/run-daily.sh` builds and ships text articles before synthesis so delivery never stalls behind cold TTS model downloads or multi-minute voice synthesis.
* Speech is attached post-publish; failed audio checks never publish and never block the underlying text.

---

## 3. Directory Layout & Module Ownership

* `src/scrapers/`: Isolated data acquisition modules inheriting from `BaseScraper`.
* `src/ai/`: Pure LLM clients, prompt formatters, scoring, enrichment, and narration text preparation.
* `src/processing/`: Profile routing, cross-source deduplication, web search tools, category thresholds.
* `src/services/`: Delivery channels, Evidence Ledger verification, and fact-checking evaluators.
* `src/models.py`: Authoritative Pydantic schemas for runtime configuration and internal data representations.
* `src/orchestrator.py`: Stage coordinator wiring the end-to-end pipeline.
* `specs/`: Spec-Driven Development documents (`spec.md`, `plan.md`, `tasks.md`).
* `deploy/`: Launchd automation, operational scripts, and deployment runbooks.
* `docs/`: Long-form architectural deep dives, live source summaries, and verification reports.
