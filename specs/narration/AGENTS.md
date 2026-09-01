# Narration SDD Guide (`specs/narration/AGENTS.md`)

This directory governs Russian neural voice track generation, text preparation, Whisper-based synthesis grading, pronunciation lexicon application, and web player integration.

## 1. Document Trio Authority & Status

- **`spec.md`**: Defines text cleaning, chunking rules, acronym unspelling, TeraTTSv2 synthesis, Whisper grading, and audio playback contracts.
- **`plan.md`**: Architecture for two-phase decoupled deployment (`run-daily.sh`), isolated host execution environment (`~/tts/.venv`), and generator/grader separation.
- **`tasks.md`**: Implementation checklist. Changes must stay in sync with `src/ai/narration.py`, `scripts/dev_narrate_article.py`, and `deploy/run-daily.sh`.
- **Hierarchy & Traceability**: `spec.md` > `plan.md` > `tasks.md`. Text preparation rules in `spec.md` map to pure functions in `src/ai/narration.py` and offline unit tests in `tests/`.

## 2. Local Non-Negotiable Invariants

1. **Speech & Publishing Decoupling**: Text articles publish to ingress immediately in Phase 1; narration then runs synchronously as Phase 2 of the same deployment script, so cold TTS models or long synthesis runs never delay the first text publish.
2. **Evaluator Segregation**: TeraTTSv2 synthesis is strictly graded piece-by-piece by a distinct model (Whisper ASR) — the TTS generator never grades its own audio.
3. **Failed Audio Rejection**: Audio failing Whisper grading or processing returns a non-zero exit code and is discarded — defective audio is never uploaded or linked on published pages.
4. **Chunk Bounds & Acronym Unspelling**: Text chunks must be strictly bounded between 120 and 400 characters, packed evenly. Acronyms are unspelled phonetically by letter name (e.g. *«GPU»* → *«джи-пи-ю»*).
5. **Playback Speed Alignment**: Audio files are pre-encoded with ffmpeg at 1.25x tempo; HTML5 audio player default playback rate is set to 1.0x.
6. **Environment Isolation**: Pure text preparation runs with the project virtualenv; only TTS synthesis and Whisper grading execute in the host's isolated `~/tts/.venv`.
