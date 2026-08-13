---
layout: default
title: Evidence Ledger shadow MVP
---

# Evidence Ledger shadow MVP

**Status:** implementation contract for the first measured version.
**Date:** 2026-08-11.
**Baseline:** see [preflight](preflight.md).
**Method:** see [methodology](methodology.md).

## Outcome

For a small number of selected technology-news items, Horizon creates an
internal, replayable report containing:

- the exact normalized pipeline input;
- at most three headline/load-bearing claims;
- fetched evidence excerpts with exact locators;
- an explicit distinction between healthy absence of evidence and system error;
- a conservative evidence status derived by versioned rules;
- an audit of factual assertions in the final enriched artifact.

No reader-visible output changes in shadow mode.

## Non-goals

The MVP does not include SQLite, migrations, leases, a planning DAG,
an independent search-service abstraction, a general origin graph,
TTL/reverification, corrections,
MCP endpoints, Schema.org output, C2PA, reverse-image search, deepfake detection,
private sources, narration invalidation or enforcement of generated prose.

Add these only after shadow measurements demonstrate the need.

## Configuration contract

The optional top-level model lives in `src/models.py`, like every other config
model in this repository. Defaults preserve the existing pipeline.

```json
{
  "verification": {
    "enabled": false,
    "publish_to_site": false,
    "max_items_per_run": 5,
    "max_core_claims_per_item": 3,
    "max_queries_per_claim": 3,
    "max_documents_per_claim": 6,
    "max_model_calls_per_item": 10,
    "timeout_seconds_per_item": 300
  }
}
```

Verification remains shadow-only unless `publish_to_site` is explicitly enabled.
That opt-in adds an experimental evidence section to article pages; it does not
change filtering, scoring, summaries, Telegram delivery, or source citations in
the generated artifact. `enforce` is not a v1 mode. No per-profile override is
needed while only the `tech-news` canary is in scope.
Code selects items whose resolved
`item.processing.classification.profile == "tech-news"`, then checks the first
`max_items_per_run` in the existing final selection order. The verifier does not
create a second ranking policy.

## Snapshot contract

### FetchedInputSnapshot

Created immediately after `fetch_all_sources()` from
`ContentItem.model_dump(mode="json")`. It proves what the pipeline received,
not what the remote server originally returned. Every fetched item gets one so
dedup lineage remains recoverable.

Required fields:

```text
schema_version
snapshot_id = sha256(schema version + canonical payload JSON bytes)
captured_at
item_id
source_type
payload
content_present
known_content_limit, when the scraper exposes one
```

`content_present=true` does not promise that the remote source was complete.
Without an exposed limit, source coverage remains unknown. Source-native raw
capture is deferred.

### SelectedInputSnapshot

Created for the final selected item after URL/topic dedup, Twitter discussion
expansion, score re-filtering and balancing, but before enrichment. It uses the
same payload/hash contract and adds the fetched snapshot IDs from which it was
derived. Claim locators point to this snapshot, so content and labels appended
by existing dedup code remain exactly anchorable.

### EvidenceSnapshot

Created only after a discovery URL passes the guarded fetch and text extraction
path. Required fields:

```text
schema_version
snapshot_id = sha256(canonical URL + normalized object hash + normalization version)
normalized_object_hash = sha256(normalized UTF-8 text)
requested_url
final_url
retrieved_at
published_at, when known
mime_type
access_status
normalizer
normalized_text
```

Search snippets never become `EvidenceSnapshot` records.

## Minimal records

### ClaimCard

```text
claim_id
selected_input_snapshot_id
source_field = title | content
source_start/source_end
source_text
normalized_claim
kind = announcement | release | quote | quantity | event | opinion | other
importance = headline | load_bearing
checkability = checkable | ambiguous | not_checkable
```

Every retained claim must round-trip to the exact `source_text` slice. Offsets
refer to Unicode code points in the named `SelectedInputSnapshot.payload` field,
before any prompt formatting. A schema-valid proposal with an inexact,
ambiguous or duplicate locator is discarded and counted in the run manifest;
other exact proposals in the same response remain usable. If none remain, the
extractor retries and ultimately fails closed.

### SearchOutcome

```text
status = ok | error
query
hits = discovery_id, rank, title, URL and snippet
error_code = unavailable | rate_limited | timeout | invalid_response, only for error
```

`status=ok` with no hits means a healthy empty search. `status=error` never
becomes `insufficient_evidence` by itself. The current adapter tries the
library's automatic backend first and uses bounded DuckDuckGo, Yahoo and Yandex
fallbacks only after an error. A healthy empty fallback is distinct from all
backends failing.

### EvidenceCard

```text
evidence_id
claim_id
evidence_snapshot_id
excerpt_start/excerpt_end
excerpt
source_class
interested_party
stance = supports | contradicts | context | irrelevant | unknown
entity_match
temporal_match
quantity_match
origin_key, optional
assessment_model
assessment_prompt_version
```

The implementation, not the model, copies URLs and excerpts from the snapshot
registry and verifies every locator. A response must still name every supplied
candidate exactly once. An inexact or ambiguous material excerpt is discarded
and counted while exact sibling assessments remain stored. Any discarded
assessment forces that claim to `insufficient_evidence`; partial model output
can never create a conclusive positive or negative verdict. If no material
assessment survives, the verifier retries and ultimately fails closed.

### VerificationReport

```text
schema_version
report_id
run_id
item_id
fetched_input_snapshot_ids
selected_input_snapshot_id
artifact_hashes by language
status per core claim
evidence IDs per claim
unchecked factual spans from each localized final artifact
search coverage and stop reason
policy/prompt/model versions
created_at
```

The stop reason is one of `sufficient`, `budget`, `no_novelty`,
`backend_error`, `source_unavailable` or `not_checkable`.

File names use `report_id`, never `item_id`; source IDs may contain characters
that are invalid in Windows paths.

## Pipeline wiring

```text
fetch
  -> capture FetchedInputSnapshots
  -> existing URL dedup, retaining a sidecar member map
  -> existing analysis
  -> existing select_digest_items()
       -> profile filtering and optional topic dedup, retaining a member map
       -> Twitter discussion expansion and score re-filter
       -> balanced final selection
  -> capture SelectedInputSnapshots
  -> existing enrichment (unchanged)
  -> shadow verification and final-artifact audit
  -> existing DailySummarizer/render/delivery (unchanged)
```

An item-level verification failure records `verification_error` and continues
the digest. Corrupt schema or storage writes fail the verification stage but do
not alter publication while the only run mode is shadow.

## Retrieval

1. Build deterministic query templates from claim kind and named entities.
2. Search for the original/primary source.
3. Search for independent reporting or a competent record.
4. Run one counterquery when the budget permits.
5. Fetch candidate URLs through the repository URL-safety path.
6. Apply redirect, byte, timeout and MIME limits while reading. A missing
   `Content-Type` is accepted only when the bounded body is valid UTF-8 with no
   binary-control signature; it is then normalized as plain text (or HTML when
   the document starts with an HTML declaration).
7. Extract bounded text and exact candidate excerpts.
8. Batch stance assessment per claim.
9. Stop on sufficient evidence, exhausted budget, no novel URLs or backend
   error.

No LLM-generated code, SQL or tool name is executable. The model may suggest a
query string; code owns budgets, URL validation, fetches and state transitions.

## Adjudication

The rule table is versioned data in code. v1 order is:

```text
not checkable                         -> not_checkable
required stage could not complete     -> verification_error
any material assessment was discarded -> insufficient_evidence
eligible support and contradiction   -> mixed_evidence
claim policy contradiction gate met  -> contradicted_by_evidence
claim policy support gate met        -> supported_by_evidence
otherwise                            -> insufficient_evidence
```

The report exposes satisfied and missing gates. Optional query/fetch failures
degrade coverage; the applicable claim policy decides whether the remaining
coverage can satisfy a gate. Deterministic derivation means reproducibility from
recorded assessments, not infallibility.

## Final-artifact audit

The audit runs over `ContentArtifact.title` and every `ContentBlock.content`.
One model call extracts candidate factual spans. Code then checks whether each
span maps to a checked claim and records unmatched spans. Shadow mode reports
violations but never rewrites or blocks the artifact.

Span-level generator annotations and corrective retries belong to a later
enforcement phase. Existing `ContentBlock.source_refs` should be reused for
evidence IDs before adding a parallel citation abstraction.

## Persistence

Use repository-native files first:

```text
data/verification/
  objects/sha256/<first-two>/<hash>
  runs/<run-id>/manifest.json
  runs/<run-id>/inputs/<hash>.jsonl
  runs/<run-id>/claims.jsonl
  runs/<run-id>/evidence.jsonl
  runs/<run-id>/reports/<report-id>.json
```

Writes use `_atomic_write_text()` or the same temporary-file/`os.replace`
pattern for bytes. JSON is canonical UTF-8 with sorted keys and compact
separators before hashing. Content-addressed objects are never overwritten.

SQLite is reconsidered only when measured revalidation or cross-run lookup
makes scanning manifests inadequate.

The entire `data/verification/` tree is gitignored before the first runtime
write.

## Security

- Source and evidence text are untrusted data, never instructions.
- Model output is schema-validated and cannot provide stored URLs or locators.
- Only public `http`/`https` destinations are fetched.
- Credentials, cookies and inherited auth headers are forbidden.
- Redirects are validated individually; body size is enforced while streaming.
- The MVP rejects private/restricted inputs rather than inventing an incomplete
  privacy policy.
- Public output remains unchanged, so no snapshots or verification internals
  are published in v1.

## Observability and budgets

Record run/item/claim IDs, stage duration, model-call count, search-call count,
documents fetched, cache reuse, discarded claim/assessment counts, stop reason
and error code. Do not report per-stage tokens until AI clients provide
stage-aware accounting.

The configuration limits are hard ceilings. Reaching one produces an explicit
incomplete result. It never guesses a conclusion. Live shadow runs still require
owner approval because they consume paid model calls.

## Test and release gates

All CI tests are offline. Minimum coverage includes:

- deterministic IDs and canonical serialization;
- atomic write recovery;
- both dedup membership maps;
- exact claim/evidence locators;
- healthy-empty search versus backend error;
- snippet rejection;
- URL/redirect/size safety;
- syndication collapsing for exact/explicit copies;
- deterministic adjudication truth table;
- unmatched final-artifact claim detection;
- disabled and shadow output parity.

Public annotation remains blocked until the evaluation in `methodology.md` is
complete and the owner records acceptable accuracy, coverage, cost and latency.

## Delivery sequence

1. **PR-0 — contracts:** these documents and verified repository map.
2. **PR-1 — discovery boundary:** typed `SearchOutcome` and bounded guarded
   document fetch.
3. **PR-2 — shadow ledger:** configuration, canonical IDs, JSONL/object storage,
   fetched/selected snapshots and both dedup maps.
4. **PR-3 — core claims:** at most three anchored claims per selected item.
5. **PR-4 — evidence report:** retrieval, stance assessment, conservative origin
   keys and rule-table adjudication.
6. **PR-5 — artifact audit and evaluation harness:** still no public effect.
7. **PR-6 — optional annotation canary:** one profile, only after the recorded
   release decision.
