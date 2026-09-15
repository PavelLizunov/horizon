# Agentic Harnesses Profile Guide (`agentic-harnesses`)

Local guide for the `agentic-harnesses` processing profile directory.

## 1. Actual Purpose & Domain

Processes developments in AI coding harnesses, agent runtimes, execution sandboxes, tool-calling frameworks, Model Context Protocol (MCP) ecosystems, and autonomous software engineering benchmarks.

- **Routes Here**: Claude Code CLI, DSH platform updates, OpenCode, Aider, Cline, OpenHands, MCP specification and server releases, sandbox isolation architectures, SWE-bench evaluations.
- **Routes Elsewhere**: Commercial API pricing and token rates (route to `paid-ai-platforms`). Theoretical AI reasoning papers (route to `frontier-research`). Token savings and KV-cache compression (route to `token-frugality`).

## 2. High-Signal Filters & Focus Areas

- **High Signal (Score 7–10)**: New agent execution capabilities, verified SWE-bench improvements, robust sandbox implementations, multi-agent coordination architectures, official MCP server releases.
- **Low Signal (Score 0–4)**: Marketing wrappers without execution ability, prompt collections, unverified hype.

## 3. Structural Schema & Web Search

- **Content Limits**: `analysis_max_chars`: 5000, `enrichment_max_chars`: 12000, `sampling`: `"head-middle-tail"`.
- **Enrichment Blocks**:
  - `summary` (required, primary, tools: `[]`)
  - `architecture_and_sandboxing` (required, tools: `["web_search"]`)
  - `developer_workflow` (optional, tools: `[]`)

## 4. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
```
