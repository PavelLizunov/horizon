# AGENTS.md — AI Layer Package Guide (`src/ai/`)

## Scope & Local Context

`src/ai/` owns all AI provider interactions, content analysis and classification, tool-augmented enrichment, programmatic digest rendering, narration preparation, token usage tracking, response parsing, and language normalization.

Key modules:
- `client.py`: Provider-neutral `AIClient` interface and multi-provider client implementations (OpenAI, Anthropic, Azure OpenAI, Gemini, Ollama, MiniMax, DeepSeek, Doubao, DashScope/Ali) with automatic fallback chaining (`ChainedAIClient`).
- `analyzer.py`: Importance scoring (`ContentAnalyzer`) using profile policies and concurrent batch processing.
- `classifier.py`: Content routing (`ContentClassifier`) to profiles via source overrides or AI catalog matching.
- `enricher.py`: Multi-block content enrichment (`ContentEnricher`) with iterative tool planning and grounding rules.
- `summarizer.py`: Pure programmatic Markdown digest rendering (`_escape_markdown`, `_safe_url`, `_pangu`, localized headers).
- `narration.py`: Pure text preparation for speech synthesis (stripping references/URLs/headings, expanding Russian numbers with `num2words` and grammatical case agreement).
- `tokens.py`: Centralized in-memory token usage tracking (`record_usage`, `get_usage_snapshot`, `reset_usage`).
- `localization.py`: Script normalization (`normalize_language`) and CJK character leak detection (`has_cjk_leak`).
- `utils.py`: Multi-strategy JSON response extraction (`parse_json_response`).
- `prompting/`: System and user prompt builders (see nested `src/ai/prompting/AGENTS.md`).

## Core Invariants & Architectural Rules

### 1. Provider Neutrality & Client Abstraction
- All AI calls must go through the `AIClient` interface (`complete(system, user, temperature, max_tokens)`). Never instantiate SDK clients directly inside pipeline components.
- Provider fallback chains (`ChainedAIClient`, `_create_chained_client`, `_create_fallback_chained_client`) handle rate limits (429), quota/billing errors, 502/503 service outages, and empty responses lazily without failing fast on startup if backup API keys are missing.
- Handle provider quirks inside `client.py`:
  - Raise non-positive temperature to `0.01` for providers requiring a positive value (`_TEMP_CLAMP`, currently MiniMax); the helper does not impose an upper bound.
  - Dynamically switch between `max_tokens` and `max_completion_tokens` for reasoning models (e.g., `o1`, `o3`, `gpt-5`).
  - Gracefully fallback when `temperature` parameter is unsupported by a provider endpoint (`_supports_temperature`).
- **Known contract/resource gaps**: OpenAI-compatible, Azure, and Gemini wrappers return SDK text fields directly even though those fields may be null while `AIClient.complete()` promises `str`; only `ChainedAIClient` rejects empty output. The interface also has no `close`/`aclose` lifecycle despite repeated client construction in the orchestrator. The `provider_chain` shorthand intentionally substitutes per-provider model/key defaults (even for the primary entry) and currently drops `enable_thinking`; use explicit `fallback_configs` for per-entry overrides until that API is reconciled.

### 2. Usage & Truncation Accounting
- Record all token usage via `record_usage(provider, input_tokens, output_tokens, cached_input_tokens)`. Include cached input token details (`prompt_tokens_details.cached_tokens`) when available.
- `_warn_if_truncated` logs warnings whenever a completion finish/stop reason matches `"length"` or `"max_tokens"`. Incomplete JSON payloads caused by token ceilings must be flagged immediately.

### 3. Structured-Output Repair & Validation
- `parse_json_response` in `utils.py` uses 5 sequential extraction strategies:
  1. Direct `json.loads`
  2. Markdown ` ```json ` code block extraction
  3. Markdown ` ``` ` code block extraction
  4. Balanced brace matching across all opening `{` positions (resilient against models repeating contract definitions before answer payloads)
  5. Regex match (`\{[\s\S]*\}`) as a last resort
- Extracted dicts must be validated through the stage's Pydantic contract (`ContentAnalysis`, `ClassificationResponse`, `GeneratedArtifact`, `GeneratedBlock`, or `ToolPlan`). Analyzer and enricher recovery paths use `tenacity`; do not assume every consumer retries automatically.

### 4. Language Leakage & Script Normalization
- Reader-facing AI output in non-CJK languages should use `has_cjk_leak(text, language)` to catch Hanzi, Kana, or Hangul leakage. The implemented enforcement point is enrichment (`_artifact_leaks`), which checks artifact titles and content blocks.
- Script normalization (`normalize_language`) uses OpenCC (`t2s`) to force Traditional Chinese to Simplified Chinese for `zh` targets.

### 5. Evaluator Segregation & Pure Programmatic Rendering
- `summarizer.py` is strictly **programmatic**: it formats Markdown digests without making LLM calls. It sanitizes unsafe URLs (`_safe_url`), escapes Markdown special characters (`_escape_markdown`), and formats typography (`_pangu`).
- `narration.py` operates completely offline to convert digest text into clean speakable Russian prose. Speech synthesis (TeraTTS) and grading (Whisper) are decoupled into host scripts/venvs.

### 6. Token & Cost Discipline
- Sizing controls (`analysis_max_chars`, `classification_max_chars`, `MAX_TOOL_REQUESTS = 3`) restrict payload context sent to LLMs.
- Inter-item throttling (`throttle_sec`) and bounded concurrency (`analysis_concurrency`, `enrichment_concurrency`) control API burst rates.

## Focused Offline Tests

All tests for `src/ai/` must run offline with mocked client responses:
- `tests/test_analyzer.py` — Scoring, batch concurrency, retry logic.
- `tests/test_azure_client.py` — Azure OpenAI endpoint handling and token fallbacks.
- `tests/test_chained_client.py` — Chained fallback logic across rate limits and provider errors.
- `tests/test_classifier.py` — Source profile overrides vs AI profile classification.
- `tests/test_enricher.py` — Tool planning, block generation, CJK leak validation.
- `tests/test_minimax_client.py` — MiniMax provider handling and Anthropic route compatibility.
- `tests/test_narration.py` — Number expansion, acronym spelling, date inflection, text stripping.
- `tests/test_summarizer.py` — Programmatic digest formatting, URL safety, markdown escaping.
