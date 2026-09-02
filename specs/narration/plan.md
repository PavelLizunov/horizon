# Narration Architecture Plan

## 1. Decoupled Two-Phase Publish
1. **Phase 1 (Immediate Text Publish)**: `run-daily.sh` builds and ships text markdown pages to ingress immediately after LLM enrichment.
2. **Phase 2 (Post-publish Narration)**: `run-daily.sh` invokes `scripts/dev_narrate_article.py` synchronously for each article. The script synthesizes audio in `~/tts/.venv`, verifies Whisper transcript match, uploads Opus (`.opus`) audio, and updates page metadata; the shell then performs the secondary site publish.

## 2. Invariants
* Grader model (Whisper) is independent of generator (TeraTTSv2).
* Chunk sizes strictly enforced (120–400 chars).
* Player default speed is 1.0x on a 1.25x pre-encoded stream.
