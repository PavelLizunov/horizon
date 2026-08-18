# Evidence Ledger & Verification Specification

## 1. Objective
Ensure factual reliability of published digest articles by extracting core verifiable claims from enriched summaries, executing targeted web searches, reading primary and secondary sources, and grading corroboration.

---

## 2. Verification Protocol
1. **Claim Extraction**: Extract 1–3 concrete, verifiable factual claims per article from final reader-facing text (using exact spans in the article's target language).
2. **Search Query Generation**: Generate targeted queries for DuckDuckGo and Google Search tools.
3. **Evidence Retrieval**: Fetch and parse candidate web pages.
4. **Corroboration Evaluation**:
   * `supported`: Claim is directly corroborated by reputable independent or official sources.
   * `partially_supported`: Partial evidence or secondary reporting.
   * `disputed`: Contradicted by authoritative evidence.
   * `unverified`: Insufficient evidence found in search window.
5. **Sanitized Public Presentation**:
   * Omit error states (`verification_error`, `check_error`, `not_checked`) from public reader views.
   * Display source links and verified notes only when valid corroboration exists.
   * Maintain token and dollar cost accounting internally without exposing estimates to readers.
