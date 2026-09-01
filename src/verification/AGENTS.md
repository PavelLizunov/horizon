# AGENTS.md — Verification Engine Package Guide (`src/verification/`)

This guide defines local rules and architectural invariants for code under `src/verification/`. Parent guidelines live in [`src/AGENTS.md`](../AGENTS.md) and root [`AGENTS.md`](../../AGENTS.md).

## 1. Package Scope & Module Map

`src/verification/` implements the Evidence Ledger engine: core claim extraction, SSRF-safe document retrieval, evidence stance assessment, deterministic adjudication, incident tracking, content-addressed ledger persistence, and a retained offline artifact-audit harness.

- `claims.py`: Extracts 1–3 core factual claims (`ClaimCard`, `claim-card/v1`) from `SelectedInputSnapshot` using `ClaimExtractor`. Validates exact character-span locators (`anchor_claims()`).
- `evidence.py`: Orchestrates evidence retrieval (`EvidenceVerifier`), evidence snapshot construction (`EvidenceSnapshot`, `evidence-snapshot/v1`), assessment card anchoring (`EvidenceCard`, `evidence-card/v1`), deterministic adjudication (`adjudicate_claim()`), public status mapping (`build_public_verification()`), token pricing reports (`build_token_usage_report()`), and run manifest assembly (`build_verification_report()`).
- `fetch.py`: SSRF-checked, redirect-safe public document fetching (`fetch_public_document()`) using `resolve_public_http_url()` from `src/url_security.py`. Uses fresh `httpx.AsyncClient` instances per redirect hop to isolate cookies and TLS state across host boundaries.
- `ledger.py`: File-native, content-addressed persistence (`ShadowLedger`) storing inputs, claims (`claims.jsonl`), evidence (`evidence.jsonl`), SHA-256 content objects (`objects/sha256/`), and run manifests (`manifest.json`) in `data/verification/`.
- `audit.py`: Retained historical/offline post-generation exact-span audit (`ArtifactAuditor`, `AuditedFactualSpan`). It maps localized prose spans to verified claim IDs, but the daily pipeline no longer invokes it as an independence guarantee.
- `incidents.py`: Persistent state machine (`update_incident_ledger()`) tracking `censorship-watch` and `vpn-engineering` event claims across state transitions (`PROVISIONAL`, `CORROBORATED`, `DISPUTED`, `RESOLVED`).
- `evaluation.py`: Offline policy and adversarial regression harness (`run_adversarial_evaluation()`) running fixtures from `tests/fixtures/verification_adversarial.json`.

## 2. API-Sensitive Contracts & Data Schemas

All schema versions and data contracts are API-sensitive and serialized into durable run records, pipeline reports, incident state, or public site payloads. Do not modify schema names or enum variants without updating validation fixtures and migration paths.

- **Schema Versions**: `claim-card/v1`, `evidence-snapshot/v1`, `evidence-card/v1`, `public-verification/v1`, `verification-report/v1`, `fetched-input/v1`, `selected-input/v1`, `verification-run/v1`, `incident-ledger/v1`.
- **Core Enums**:
  - `ClaimKind`: `"announcement"`, `"release"`, `"quote"`, `"quantity"`, `"event"`, `"opinion"`, `"other"`.
  - `ClaimImportance`: `"headline"`, `"load_bearing"`.
  - `ClaimCheckability`: `"checkable"`, `"ambiguous"`, `"not_checkable"`.
  - `EvidenceStance`: `"supports"`, `"contradicts"`, `"context"`, `"irrelevant"`, `"unknown"`.
  - `SourceClass`: `"original"`, `"competent_record"`, `"independent_reporting"`, `"interested_party"`, `"unknown"`.
  - `VerificationStatus`: `"supported_by_evidence"`, `"contradicted_by_evidence"`, `"mixed_evidence"`, `"insufficient_evidence"`, `"not_checkable"`, `"verification_error"`.
- **Span Locator Invariant**: `source_text` spans in claims, evidence cards, and artifact audit spans must be exact, contiguous, non-paraphrased substrings within declared source fields (`title`, `content`, or normalized text). Locators that fail exact string matching or exhibit ambiguity must be rejected or discarded.

## 3. Security & Safety Invariants

1. **SSRF & URL Safety**: All external HTTP fetching in `fetch.py` MUST route through `resolve_public_http_url()` from `src/url_security.py`. Requests to internal, private, loopback, or link-local IP addresses are blocked (`UnsafeURLError` -> `security_blocked`). Redirects must re-evaluate destination IP addresses and create isolated HTTP client sessions per hop.
2. **Evaluator Segregation & Data Isolation**: Claim, evidence, and artifact text is enclosed by stage-specific untrusted-data markers (`UNTRUSTED_NEWS_DATA_START`, `UNTRUSTED_EVIDENCE_DATA_START`, `UNTRUSTED_ARTIFACT_DATA_START`). These models must never inherit, view, or rely on generation prompt context.
3. **Source Independence & Origin Keys**: Interested-party sources cannot independently corroborate event or quantity claims. `origin_key` values (`url:...`, `report:...`, `copy:...`) enforce source independence to prevent syndicated content or mirror sites from satisfying multi-source corroboration gates.

## 4. Bounded Costs & Resource Limits

Verification activities are strictly resource-capped via `VerificationConfig` (`src/models.py`) and runtime guards:

- **LLM Call Limits**: `ItemVerificationBudget` enforces a strict ceiling (`max_model_calls_per_item`, default 10) shared across claim extraction, stance assessment, and artifact auditing.
- **Search & Fetch Caps**: Query generation is capped by `max_queries_per_claim` (default 3); document fetching is capped by `max_documents_per_claim` (default 6).
- **HTTP Fetch Limits**: `fetch_public_document()` enforces a 2 MB content ceiling (`max_bytes`), a 30 s timeout (`timeout_seconds`), at most 5 redirects (`max_redirects`), and whitelisted text/JSON MIME types (`DEFAULT_MIME_TYPES`).

## 5. Public Error & Usage Presentation

1. **Error Hiding**: Readers must never see internal failure states (`verification_error`, `check_error`, `check_failed`, `not_checked`) or scary warning banners on live article pages. Unverified claims degrade gracefully by omitting public banners (`build_public_verification()`).
2. **Current Split Behavior**: Article banners do not render token or cost details, but `build_public_verification()` may carry `token_usage`, and `scripts/dev_verification_status.py` currently publishes usage on the public checks page with `include_usage=True`.
3. **Unresolved Policy Conflict**: The public checks behavior and its regression test/changelog conflict with the constitution and older specs that say raw token/dollar estimates stay private. Do not silently remove, broaden, or rename this output; an owner-approved contract decision must update policy docs, implementation, and tests together.

## 6. Content Immutability & Incident Semantics

- **Content-Addressed Storage**: `ShadowLedger` writes payload and text objects into `objects/sha256/xx/hash`. Existing immutable object files must match content byte-for-byte; discrepancies raise `LedgerCorruptionError`.
- **Incident State Machine**: Event claims for `censorship-watch` and `vpn-engineering` profiles update a durable incident ledger (`update_incident_ledger()`). Incidents transition through deterministic states (`PROVISIONAL`, `CORROBORATED`, `DISPUTED`, `RESOLVED`) and schedule periodic re-verification (`next_check_at`). The final replace is atomic, but the preceding load/merge/write transaction has no lock, so overlapping writers can lose updates.

## 7. Verification & Offline Testing

All verification changes must be validated offline without network access or live API calls:

- **Pytest Suite**: Run `.venv/bin/pytest tests/test_verification_*.py -v` (or `uv run pytest tests/test_verification_*.py -v`).
- **Adversarial Regression Harness**: Run offline adversarial evaluation via `src/verification/evaluation.py` using `tests/fixtures/verification_adversarial.json`.
