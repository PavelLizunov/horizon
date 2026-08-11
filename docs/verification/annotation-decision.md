---
layout: default
title: Evidence Ledger annotation decision
---

# Evidence Ledger annotation decision

**Decision date:** 2026-08-11.
**Decision:** do not add a public annotation canary. Keep the feature disabled
by default and shadow-only; the measured deployment may enable the internal
ledger deliberately.
**Owner approval for a public canary:** not requested or granted.

## Recorded gates

| Measure | Recorded result | Release gate | Verdict |
|---|---|---|---|
| Offline adversarial policy precision | 10/10 cases; 0 false support | 0 false support in the adversarial corpus | Pass for this fixture only |
| Blinded real-news accuracy | Not measured | At least 100 stories and 300 claims | Missing |
| Conclusive coverage / abstention | Final paid sample: 4 supported, 2 insufficient, 1 not-checkable, 0 errors from 7 claims | Owner-selected threshold after a representative shadow sample | Technical sample passes; threshold missing |
| Added end-to-end latency | Five repeated full runs measured 400.6-961 seconds; the final five reports were 13.2-123.6 seconds each | Owner-selected acceptable bound | Measured, threshold missing |
| Added token and monetary cost | Final run 318,932 tokens; at least 1,644,257 metered tokens across implementation probes and runs | Owner-selected acceptable bound and provider-credit measurement | Measured tokens; monetary threshold missing |
| Citation/locator correctness | Exact round-trip tests pass; final run discarded 2 inexact claim proposals and 3 inexact evidence excerpts | Human citation review on the real-news sample | Automated gate passes; human gate missing |
| Public-output parity | Disabled mode writes nothing; shadow audit does not mutate artifacts or citations | No reader-visible change before approval | Pass |

The original adversarial corpus remained free and offline. Five paid shadow
runs and targeted reproductions are recorded separately in
`evaluation-results.md`. They establish a technical operating range, not an
accuracy estimate for real news.

## Consequence

No public badge, label, `ClaimReview`, renderer branch or annotation mode is
implemented. The technical blockers from the first paid run were fixed: the
final run completed claim extraction and artifact audit for 5/5 items, with no
verification or search errors. The internal ledger may therefore run in shadow
to collect the required real sample.

A future public canary is still a new decision. It requires the blinded
100-story/300-claim review, raw confusion counts, a human citation review and
owner-selected coverage, latency and cost thresholds. Technical reliability
does not substitute for those quality gates.

This negative decision completes the shadow-MVP experiment without claiming
that the system is ready for readers.
