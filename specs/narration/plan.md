# Narration Architecture Plan

## 1. Decoupled Two-Phase Publish
1. **Phase 1 (Immediate Text Publish)**: `run-daily.sh` builds and ships text markdown pages to ingress immediately after LLM enrichment.
2. **Phase 2 (Asynchronous Narration)**: `scripts/dev_narrate_article.py` synthesizes audio in `~/tts/.venv`, verifies Whisper transcript match, uploads MP3, updates page metadata, and triggers a secondary deploy.

## 2. Invariants
* Grader model (Whisper) is independent of generator (TeraTTSv2).
* Chunk sizes strictly enforced (120–400 chars).
* Player default speed is 1.0x on a 1.25x pre-encoded stream.
