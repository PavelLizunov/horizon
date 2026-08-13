---
layout: default
title: Evidence Ledger publication decision
---

# Evidence Ledger publication decision

## Current decision — 2026-08-14

The owner approved reader-visible source coverage on article pages and on the
site's `/checks/` page. This is not a `true`, `false`, `verified`, or universal
fact-check badge. It reports only the selected key claims, the sources retrieved
for them, and the limits of that run.

Public states are deliberately narrow:

- `complete`: the selected key claims reached their applicable source-policy
  outcomes;
- `partial`: at least one selected claim has insufficient coverage;
- `provisional`: a fresh event has not yet had time to acquire stable,
  independent corroboration;
- `check_error`: a required check timed out or failed;
- `not_applicable`: no suitable factual key claim was extracted;
- `not_checked`: the article was outside the bounded daily sample.

Claim wording depends on claim type. An official announcement proves that an
announcement exists; it does not prove every assertion inside it. A release can
be tied to a release record. A field event needs a competent record or two
distinct reporting origins. A vendor quantity is labelled as a primary/vendor
report unless its policy gate is satisfied. Opinion and personal experience are
attributed, not converted into facts.

## Why the first public design was retired

The 2026-08-13 live run showed that the second final-artifact audit was both
expensive and untrustworthy as an independence mechanism: the same model wrote,
extracted, assessed, and audited the text. Four of five audits failed, while the
one successful audit found 23 uncovered factual spans. The page still described
those results as completed.

The runtime now extracts claims from the final reader-visible artifact and does
one evidence assessment path. The old audit code and fixture remain for
historical offline evaluation, but the daily pipeline no longer spends tokens
on it or presents it as a safety guarantee.

## Remaining accuracy gate

The blinded review of at least 100 stories and 300 claims has not been
completed. The public feature is therefore an owner-approved transparency
canary, not a validated fact-checking product. Exact locators, conservative
adjudication, explicit errors, and public source links reduce the risk; they do
not establish real-world accuracy by themselves.

Provider token counts are shown exactly when the gateway reports them. Dollar
figures are estimates using the configured base DeepSeek API prices, including
the configured cached-input rate. They are not an OpenCode invoice or a claim
about the exact amount deducted from a subscription quota.
