---
layout: default
title: Evidence Ledger implementation
---

# Evidence Ledger implementation

**Current contract:** 2026-08-14.
**Method:** see [methodology](methodology.md).
**Publication decision:** see [annotation decision](annotation-decision.md).

## Outcome

For a bounded daily sample, Horizon records a replayable evidence report and can
publish a cautious source-coverage section. The report contains:

- the fetched input lineage;
- the exact final reader-visible title and prose used for claim extraction;
- at most three headline or load-bearing claims;
- bounded public-document snapshots and exact evidence excerpts;
- a deterministic claim-type policy outcome;
- provider-reported token counts and an optional configured-price estimate.

It does not decide universal truth, grade the whole article, execute model-made
code, or turn a search snippet into evidence.

## Configuration

```json
{
  "verification": {
    "enabled": false,
    "publish_to_site": false,
    "input_price_per_million_usd": null,
    "cached_input_price_per_million_usd": null,
    "output_price_per_million_usd": null,
    "max_items_per_run": 5,
    "max_core_claims_per_item": 3,
    "max_queries_per_claim": 3,
    "max_documents_per_claim": 6,
    "max_model_calls_per_item": 10,
    "timeout_seconds_per_item": 300
  }
}
```

`enabled` records the private ledger. `publish_to_site` additionally attaches
the small public payload to article pages. Neither option changes article
selection. Prices must match the active model's public API tariff; the result is
an estimate, not provider billing.

The sample prioritizes factual reader profiles in this order:
`censorship-watch`, `vpn-engineering`, `finance-news`, `tech-news`, `video`.
Within a profile, final digest order is preserved.

## Pipeline placement

```text
fetch
  -> immutable fetched snapshots
  -> URL dedup + analysis + profile selection + topic dedup + balancing
  -> enrichment creates the final localized article
  -> selected snapshot replaces title/content with that final artifact
  -> claim extraction
  -> safe public retrieval + evidence assessment + rule adjudication
  -> private report + small public payload
  -> article/site rendering
```

The previous second model call that audited the generated artifact is not in the
runtime. Claims now come directly from the artifact the reader sees. This is
cheaper and removes a misleading same-model self-review, while preserving the
original fetched snapshot and dedup lineage for replay.

## Immutable records

### Fetched input

Every fetched `ContentItem` is serialized before dedup. Its ID and object hash
use canonical UTF-8 JSON. A selected item retains all fetched member IDs from URL
and topic dedup.

### Selected input

The selected snapshot is captured after enrichment. Its `title` and `content`
are the localized artifact title and ordered block titles/content. Claim
locators therefore point to the published prose, not to an earlier source-only
draft.

### Claim

Each retained claim carries an exact `source_field`, Unicode start/end offsets,
copied `source_text`, normalized claim, kind, importance, and checkability. Code
rejects missing, ambiguous, duplicate, or inexact spans. The maximum is three.

Kinds are `announcement`, `release`, `quote`, `quantity`, `event`, `opinion`,
and `other`.

### Evidence

URLs pass the shared public-address guard on every redirect. Fetching has status,
MIME, byte, and wall-clock limits and inherits no credentials or cookies. Search
snippets are discovery-only. Normalized documents are content-addressed; a
material evidence card must copy one unambiguous exact excerpt.

Source classes are `original`, `competent_record`, `independent_reporting`,
`interested_party`, and `unknown`. Exact copies share one origin. Distinct
independent-report URLs get distinct conservative reporting origins; unknown
independence never counts.

## Retrieval budget

Announcements, releases, quotes, and quantities fetch the original source plus
at most one discovery query. Events and `other` claims may use the configured
query ceiling because they need corroboration and counter-evidence. All kinds
share the configured document and per-item model-call ceilings.

Healthy empty search, provider failure, access denial, unsupported MIME, and
timeout remain distinct recorded outcomes. Exhausting a required stage produces
an explicit error, not a negative claim result.

## Deterministic adjudication

The rule order is:

```text
not checkable                         -> not_checkable
required stage failed                -> verification_error
eligible support and contradiction   -> mixed_evidence
direct policy contradiction          -> contradicted_by_evidence
claim-type support gate passed       -> supported_by_evidence
otherwise                            -> insufficient_evidence
```

An event needs a competent record or two distinct eligible origins. A quantity
needs a matching direct source with matching scope. Announcements, releases,
and quotes may use their direct original record for attribution. Interested
parties do not prove unrelated event or performance claims.

## Public vocabulary and freshness

The public payload contains claim text, kind, raw status, type-aware public
status, source URL/stance/class, `checked_at`, source age, optional
`next_check_at`, and token usage. It never publishes stored document text,
excerpts, prompts, search queries, cookies, or headers.

Fresh unresolved `event` and `other` claims are `provisional`. Their next review
points are 24 and 72 hours after publication. Older insufficient events become
`insufficient` rather than staying permanently "fresh". Official announcements
and release records can be attributed immediately, without claiming that every
broader assertion is true.

Article state is derived from results: errors win, then no-applicable-claim,
then provisional, then partial, then complete. Articles outside the bounded
sample are explicitly `not_checked`.

## Incident history

`data/incidents.json` stores event claims from `censorship-watch` and
`vpn-engineering`. It records a stable claim fingerprint, first/last seen,
last checked, next check, source item IDs/URLs, and state history:

```text
PROVISIONAL -> CORROBORATED | DISPUTED -> RESOLVED
```

`RESOLVED` requires explicit item metadata; the system does not infer recovery
from silence. A later daily observation of the same event advances its state.
The generated `/checks/` page shows the latest incident state and timestamps.

## Persistence and failure behavior

```text
data/verification/
  objects/sha256/<prefix>/<hash>
  runs/<run-id>/manifest.json
  runs/<run-id>/inputs/<hash>.jsonl
  runs/<run-id>/claims.jsonl
  runs/<run-id>/evidence.jsonl
  runs/<run-id>/reports/<report-id>.json
data/incidents.json
```

Writes use same-directory temporary files and atomic replacement. The data is
gitignored. Verification and incident-history failures are visible but do not
stop the digest from publishing; a failed check is rendered as interrupted, not
as completed.

## Tests and release boundary

All CI tests are offline. Coverage includes canonical IDs, atomic recovery,
dedup lineage, exact locators, guarded fetching, search error semantics, exact
copy collapse, independent event origins, claim-type adjudication, freshness,
incident transitions, disabled-mode parity, public wording, and token pricing.

The owner has approved a cautious public canary. The missing blinded
100-story/300-claim review still prevents describing this as a validated
fact-checking system.
