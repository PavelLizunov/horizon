# Speech & Audio AI Profile Guide (`speech-ai`)

Local guide for the `speech-ai` processing profile directory.

## 1. Actual Purpose & Domain

Processes technical developments in speech synthesis (TTS), speech recognition (ASR), speaker diarization, voice cloning, speech normalization (front-ends), and local video dubbing pipelines.

- **Routes Here**: Fish-Speech, Qwen3-TTS, TeraTTSv2, VibeVoice ASR, Whisper optimizations (faster-whisper, mlx-whisper), Sber GigaAM, Pyannote diarization, Demucs audio separation.
- **Routes Elsewhere**: General AI model architectures and reasoning (route to `frontier-research`). Local GPU server infrastructure and Proxmox (route to `homelab-infra`). Commercial API subscription pricing (route to `paid-ai-platforms`).

## 2. High-Signal Filters & Focus Areas

- **High Signal (Score 7–10)**: Open weights releases with Russian/English support, low RTF streaming ASR/TTS, zero-shot voice cloning breakthroughs, Pyannote diarization releases.
- **Low Signal (Score 0–4)**: Consumer voice changer apps, novelty AI songs, marketing press releases without model weights or technical specs.

## 3. Structural Schema & Web Search

- **Content Limits**: `analysis_max_chars`: 4000, `enrichment_max_chars`: 10000, `sampling`: `"prefix"`.
- **Enrichment Blocks**:
  - `summary` (required, primary, tools: `[]`)
  - `model_architecture` (required, tools: `["web_search"]`)
  - `audio_pipeline_relevance` (optional, tools: `[]`)

## 4. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
```
