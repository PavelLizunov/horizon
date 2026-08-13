---
layout: default
title: Evidence Ledger methodology
---

# Evidence Ledger methodology

Evidence Ledger does not decide universal truth. It records whether a bounded,
atomic claim is supported or contradicted by the evidence that this run could
retrieve, under a versioned policy.

## Questions kept separate

For every core claim the report distinguishes:

1. **Attribution** — did a named actor publish or say this?
2. **Occurrence** — is there direct evidence that the event happened?
3. **Corroboration** — are there independent evidence origins?
4. **Accuracy** — do entity, time, place, quantity, unit and scope match?
5. **Interpretation** — does the evidence justify the causal or evaluative
   wording?

An official announcement can settle attribution without settling occurrence or
accuracy. Repetition across domains can still represent one reporting origin
and one underlying evidence origin.

## Evidence rules

- No source means no evidential conclusion. Model memory is not evidence.
- A search snippet is discovery material only.
- Displayed evidence has a stored normalized snapshot and an exact locator.
- Interested-party material may prove its own statement, but not every
  proposition inside that statement.
- Tool failure, access denial and an empty healthy search are different states.
- Unknown independence is not counted as independent.
- Exact quotations must match the stored snapshot. A translation is labelled as
  a translation and retains the original wording.
- The final status is produced by versioned rules over recorded assessments.
  The assessments remain fallible model or heuristic outputs.

## v1 status vocabulary

The shadow MVP deliberately avoids `TRUE`, `FALSE`, `VERIFIED`, probability
scores and `LIKELY_*` labels.

| Status | Meaning |
|---|---|
| `supported_by_evidence` | The configured support gate passed. |
| `contradicted_by_evidence` | The configured contradiction gate passed. |
| `mixed_evidence` | Eligible material materially supports and contradicts the claim. |
| `insufficient_evidence` | Retrieval worked but no conclusive gate passed. |
| `not_checkable` | The wording is opinion, prediction, preference or irreducibly ambiguous. |
| `verification_error` | A required stage could not produce a usable result, so no evidential conclusion is emitted. |

Public wording, when annotation is eventually enabled, must say “supported by
the collected evidence”, not “proven true”.

Failure of one optional query or candidate fetch is recorded as degraded
coverage. It becomes `verification_error` only when a required stage cannot
complete; a partially successful run may reach an evidential status only when
the applicable policy gate does not require the failed coverage.

## Minimal source policy

The MVP starts with technology-news claims only:

- announcement or software release: original announcement, repository release,
  changelog, registry or artifact;
- exact quote: original document, transcript or recording;
- benchmark or quantity: value, unit, period, denominator and test conditions;
- event occurrence: competent direct record or two clearly independent evidence
  origins.

Other policies, medical/legal conclusions, causal adjudication and multimodal
verification are deferred until the text pipeline is measured.

## Independence in v1

There is no general provenance graph. The implementation may collapse exact
copies, canonical variants, explicit syndication and articles that name the same
underlying document. Anything else remains `independence_unknown` and does not
increase the independent-origin count.

## Human evaluation

Before any public badge:

- evaluate at least 100 diverse stories and 300 headline/load-bearing claims;
- hide the automatic status from the reviewer until the human label is saved;
- report raw confusion counts, citation correctness, conclusive coverage,
  abstention, model/prompt versions, wall time and added model calls;
- include adversarial cases for syndication, correction, paywall, provider
  outage, prompt injection, unit/scope mismatch and fabricated final prose;
- require zero false `supported_by_evidence` outcomes in the adversarial corpus;
- do not choose a production precision/coverage threshold until the shadow data
  exists and the owner records the decision.

The original design brief cites methodological ideas from corroborate-mcp,
giasip-skills, bullshit-detector, FIRE, ProgramFC, Loki/OpenFactVerification,
AVeriTeC, DEFAME, OpenFactCheck, W3C PROV, Schema.org ClaimReview and C2PA. They
are references, not runtime dependencies. No third-party code is copied without
checking its exact license and attribution requirements.

## Viewing the latest result

On the machine that runs Horizon, print a compact summary of the newest attempt
and the last completed evidence run:

```bash
.venv/bin/python scripts/dev_verification_status.py
```

Add `--json` for machine-readable output. The report remains internal while the
human-review release gates are unmet; it does not add badges to public articles.

## Privacy and retention

The shadow MVP excludes private/restricted sources. It stores normalized text
needed for audit, not complete media or paywalled copies, and never publishes
snapshots, prompts, private URLs, cookies, headers or search queries. Retention,
reverification and deletion workflows are post-MVP work and must be specified
before private sources are admitted.
