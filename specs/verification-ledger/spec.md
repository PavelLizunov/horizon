# Evidence Ledger & Verification Specification

## 1. Objective
Ensure factual reliability of published digest articles by extracting core verifiable claims from enriched summaries, executing targeted web searches, reading primary and secondary sources, and grading corroboration.

---

## 2. Verification Protocol
1. **Claim Extraction**: Extract 1–3 concrete, verifiable factual claims per article from final reader-facing text (using exact spans in the article's target language).
2. **Search Query Generation**: Generate targeted queries and execute them through `WebSearchTool`, which uses DDGS automatic routing followed by the explicit `duckduckgo`, `yahoo`, and `yandex` fallback backends.
3. **Evidence Retrieval**: Fetch and parse candidate web pages.
4. **Corroboration Evaluation**: Current versioned reports serialize exactly one `VerificationStatus` value:
   * `supported_by_evidence`: available evidence supports the claim.
   * `contradicted_by_evidence`: authoritative evidence contradicts the claim.
   * `mixed_evidence`: material evidence supports and contradicts the claim.
   * `insufficient_evidence`: the bounded search did not establish a verdict.
   * `not_checkable`: the claim is opinion or cannot be verified as a factual proposition.
   * `verification_error`: the bounded verification process failed operationally.
   > Earlier design documents used `supported`, `partially_supported`, `disputed`, and `unverified`. Those proposal terms are not current serialized values; readers of historical artifacts must not treat them as aliases with a guaranteed one-to-one mapping.
5. **Sanitized Public Presentation**:
   * Omit operational error states (`verification_error`, `check_error`, `not_checked`) from public reader views.
   * Display type-aware coverage labels (including conservative `provisional` or `insufficient` outcomes) and include only validated public source links.
   * Keep token and dollar cost accounting internal unless the open policy decision below changes this requirement.

## 3. Open Usage-Publication Decision

Article banners omit token and cost estimates as required above. The generated
public `/checks/` page nevertheless calls
`verification_summary_markup(..., include_usage=True)`, and regression tests and
the changelog preserve that output. This conflict is intentionally documented,
not resolved here. Until the owner approves one policy, keep the tested split;
a resolution must update the constitution, this spec, implementation, tests,
and changelog together.
