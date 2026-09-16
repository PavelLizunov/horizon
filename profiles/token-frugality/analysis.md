# Evaluation goal

Evaluate whether the item provides a verified, measurable methodology, tool, or architectural breakthrough for reducing token costs, shrinking KV-cache footprint, or accelerating LLM inference throughput.

# Scoring rubric

- **9-10: Major efficiency breakthrough.** Industry-standard leap in inference efficiency: seminal KV-cache compression algorithms, universal prompt caching standards, major MTP speculative decoding speedups (>1.5x throughput at zero quality loss), or foundational vLLM/ExLlamaV3 architectural milestones.
- **7-8: High practical value.** Substantial token/cost reduction techniques (>30% savings), robust context pruning libraries, verified model tier cascade frameworks with frugality guarantees, or optimized INT4/FP8 KV-cache implementations.
- **5-6: Useful optimization & community benchmarks.** Practical serving optimizations, empirical benchmarks from community practitioners (e.g. r/LocalLLaMA throughput tests with speculative decoding like DFlash2, GSQ/GGUF calibrations, long-context offloading), prompt prefix restructuring guides, or comparative engine measurements.
- **3-4: Minor gain.** Small localized optimization, hyper-specialized script with narrow applicability, or rehash of well-known prompt engineering advice.
- **0-2: Noise.** Trivial advice, promotional spam, completely unverified marketing claims without any numbers or setup details.
