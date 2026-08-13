---
layout: default
title: Evidence Ledger offline evaluation
---

# Evidence Ledger offline evaluation

> Historical measurement record. On 2026-08-14 the daily runtime stopped using
> the final-artifact audit and started extracting claims from the final article
> directly. The old audit fixtures remain offline regression material; the old
> provider route described below is not configured in production.

**Recorded:** 2026-08-11.
**Scope:** deterministic policy and artifact-audit regression only.
**Command:** `uv run --offline python scripts/dev_evaluate_verification.py`

## Result

- 10 of 10 adversarial cases passed.
- 0 false `supported_by_evidence` outcomes.
- No network, provider API, private data or paid model call was used.

The corpus covers exact syndication, corrections, unavailable/paywalled
material, provider outage, quantity/unit mismatch, healthy empty discovery,
prompt injection, fabricated final prose, direct contradiction and ambiguous
wording. Its source is
`tests/fixtures/verification_adversarial.json`; CI reruns the same cases.

## Interpretation

This result shows that the versioned rule table and exact-span audit retain the
specified conservative behavior on the recorded fixtures. It is not an
accuracy or coverage estimate for real news. The required blinded human review
of at least 100 stories and 300 claims has not been performed. The first live
latency, token and coverage observations are recorded below.

## First paid shadow run

**Recorded:** 2026-08-11.
**Model:** `deepseek-v4-flash` through the retired compatible gateway used at
the time for analysis, enrichment, claim extraction, evidence assessment and
artifact audit.
**Safety:** email, webhook delivery and search indexing were disabled; runtime
summaries and seen state were isolated. The evidence ledger was retained.

The end-to-end run completed successfully in 961 seconds and produced 16
temporary article pages. It used 356,617 model tokens (198,710 input and
157,907 output). The shadow sample was capped at five technology-news items:

- 5 reports, 8 persisted claims and 21 persisted evidence records;
- 25 documents attempted, 17 fetched and normalized, 5 search calls;
- claim extraction succeeded for 3/5 items; two model responses were invalid;
- claim results: 4 `insufficient_evidence`, 2 `not_checkable`, and 2
  `verification_error`;
- artifact audit succeeded for 2/5 items, returned invalid responses for two,
  and timed out for one;
- no claim reached a conclusive supported or contradicted status.

One search call failed as unavailable. Fetch failures were kept explicit: two
access-denied, two network errors, one timeout and two unsupported MIME types.
None were converted into negative evidence.

The provider also reported one response truncated at the configured output
limit. A five-item extraction probe with hybrid-model thinking disabled and an
8,192-token response ceiling improved latency from 3.5-33.0 seconds to
0.8-4.0 seconds and succeeded on 4/5 items, using 10,059 input and 624 output
tokens. A repeat diagnostic on the same snapshots succeeded on 3/5: one
response violated the schema and one supplied a non-exact source locator. It
used another 10,059 input and 1,012 output tokens.

The full run and follow-up probes used 378,371 tokens in total. This was a
functional integration result, not a release result, and triggered the
structured-output remediation below.

## Remediation and repeated paid runs

All repeated runs kept public delivery and indexing disabled and used
`deepseek-v4-flash` for every model stage. Thinking was disabled and the
response ceiling was raised to 8,192 tokens. Structured claim extraction,
evidence assessment and artifact audit retry at most three times while still
sharing the per-item call budget.

| Run | Change under test | Wall time | Tokens | Extraction / audit | Claim outcomes |
|---|---|---:|---:|---|---|
| 2 | Structured retries and larger per-item budget | 400.6 s | 275,526 | 4/5 / 5/5 | 2 insufficient, 1 error |
| 3 | Preserve exact claim proposals while discarding an inexact sibling | 459.3 s | 259,363 | 5/5 / 5/5 | 2 supported, 2 insufficient, 2 not-checkable, 2 search errors |
| 4 | Search backend fallback and strict headerless-text detection | 600.5 s | 320,065 | 5/5 / 5/5 | 4 supported, 2 insufficient, 1 assessment-locator error |
| 5 | Discard inexact evidence excerpts and forbid a conclusive result for that claim | 595.5 s | 318,932 | 5/5 / 5/5 | 4 supported, 2 insufficient, 1 not-checkable, 0 errors |

The final run ID was
`20260811T164625-a975ed07a87e4e0b9987d08a7ee70fbb`. Its five reports
contained seven claims and 38 evidence records: 27 normalized snapshots and 11
exact excerpt cards. Seven searches completed with no typed search error. Of 36
documents attempted, 27 were fetched; one oversized response, one access denial
and three timeouts remained explicit coverage limitations.

DeepSeek supplied two inexact claim proposals and three inexact evidence
excerpts in the final run. Code discarded and counted all five. A claim with a
discarded evidence assessment cannot receive a conclusive supported or
contradicted status, even when other exact excerpts exist. The five final
artifact audits completed successfully and recorded five unmatched factual
spans for later human review.

The known metered investigation total is at least 1,644,257 model tokens. One
locator-classification call did not expose usage, so no fabricated exact grand
total is reported. Provider-credit cost remains unavailable because accounting
is provider-level and the Alibaba credit coefficient was not measured.

## Interpretation after remediation

The technical shadow path is now reliable enough for continued internal data
collection: the final run had no extraction, assessment, audit or search error,
and every imperfect locator failed closed. This does not pass the public release
gate. The blinded review of at least 100 stories and 300 claims is still absent,
and five unmatched final-artifact spans demonstrate why reader-visible badges
remain premature.
