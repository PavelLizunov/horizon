# AI Workflows, SDD & Categorization Specification

## 1. Objective
Establish profile-driven evaluation, category scoring, and automated grouping for emerging AI engineering practices, Spec-Driven Development (SDD), agentic systems, developer tools, and VPN/network security.

---

## 2. Category Hierarchy & Threshold Routing

### 2.1 Category Threshold Overrides (`category_thresholds`)
Allows per-category threshold tuning within a shared profile:
* `llm`: 4.5 / 10
* `ai-tools`: 4.5 / 10
* `ai-workflows`: 4.5 / 10
* `sdd` / `spec-driven-development`: 4.5 / 10
* General `tech-news`: 6.5 / 10

### 2.2 Editorial Groupings
1. **Инструменты и подходы в использовании ИИ (`ai-tools-workflows`)**:
   * Tags: `sdd`, `specdrivendevelopment`, `aitools`, `aiworkflow`, `aidev`, `aicoding`, `promptengineering`, `agentic`, `devtools`, `vibecoding`.
   * Focus: Methodologies for software engineering with LLMs and AI agents, specification frameworks (Spec-Kit), architectural patterns, workflow automation.
2. **Искусственный интеллект и LLM (`llm`)**:
   * Focus: Foundation model releases, benchmarks, fine-tuning techniques, inference architectures.
3. **Россия: блокировки и ограничения (`ru-censorship`, `ru-field-report`)**:
   * Focus: Network access anomalies, DPI/TSPU filters, community reports from 4PDA/Telegram.
4. **VPN: технологии и протоколы (`vpn-engine`, `vpn-protocol`)**:
   * Focus: Xray, VLESS, sing-box, AmneziaWG, Hysteria, protocol circumvention.
