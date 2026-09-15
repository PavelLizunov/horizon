# Token frugality & inference optimization profile

Use this profile for concrete methodologies, benchmarks, tools, and runtime techniques designed to minimize token consumption, optimize KV-cache memory, accelerate inference throughput, and reduce LLM operating costs.

Typical items include:
- Prompt caching architectures: Anthropic Prompt Caching, OpenAI Prefix Caching, DeepSeek Context Caching, prompt structure optimization (prefix stability, cold cache isolation).
- KV-cache compression and quantization: FP8, INT4, Hadamard transforms, PagedAttention, vLLM, SGLang, and ExLlamaV3 memory optimization.
- Speculative decoding & Multi-Token Prediction (MTP): MTP architectures in DeepSeek-V3/R1 and Qwen 3.8, speculative drafting (Medusa, EAGLE), draft-model cascades, and GPU throughput acceleration.
- Context pruning and compaction: selective context compaction, dynamic history trimming, anti-slop prompt stripping, hierarchical map-reduce summarization, semantic deduplication, and minimal prompting (Ponytail/YAGNI discipline).
- Model tier routing & cascades: Frugality Assurance, adaptive routing (cheap/fast models for routine turns with escalation to frontier reasoning models on ambiguity or recovery).
- Inference serving engines: ExLlamaV3, vLLM, SGLang, llama.cpp, Apple Silicon MLX optimization.

Do not use this profile for generic tips on "how to write prompts", non-empirical cost advice, general AI product announcements without efficiency metrics, or academic papers with no measurable inference gains.
