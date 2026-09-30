# Narration Specification

## 1. Objective
Generate high-quality Russian spoken voice tracks for all published digest articles using local neural text-to-speech synthesis (TeraTTSv2 / `ru_f1`), with Whisper-based independent grading, customized pronunciation lexicons, and zero-stall web publishing.

---

## 2. Requirements

### 2.1 Text Preparation
* Pure Python module `src/ai/narration.py`.
* Strip Markdown syntax, URLs, citations, code fences, and parenthetical artifacts.
* Unspell tech acronyms phonetically by letter name (*«GPU»* → *«джи-пи-ю»*).
* Apply vetted static pronunciation lexicon (`_TERA_PRONUNCIATIONS` in `src/ai/narration.py`), with optional candidate review via `data/pronunciation-reviews/`.
* Segment text into balanced chunks strictly within 120–400 characters.

### 2.2 Synthesis & Independent Grading
* Engine: TeraTTSv2 (`ru_f1` voice).
* Isolated execution in dedicated venv (`~/tts/.venv`).
* Grade synthesis piece-by-piece using Whisper ASR against source chunk text.
* Uncorroborated or defective audio is rejected and never published.

### 2.3 Audio Delivery
* Encode audio at 1.25x tempo with ffmpeg.
* Upload Opus (`.opus`) audio to static SSH storage or Cloudflare R2 bucket.
* Attach accessible custom HTML5 audio player to MkDocs article pages.

## 3. Player Availability Fix

### Intended result and scope
* Publish each validated article's player before synthesizing the next article,
  rather than waiting for all tracks in the issue. Text must still publish first.
* Reuse the Linux Whisper grader once per checker name in the narration process;
  preserve the independent model, chunk checks, retries, and final-file grading.
* Add optional `--after-attach COMMAND [ARG ...]` to `--speak-dir --attach`.
  Run the operator-supplied argv without a shell only after upload verification
  and successful attachment. Existing invocations remain unchanged.
* Missing pages or invalid attachment markup must report failure, not trigger
  a success hook without an attached player.
* A hook failure stops that narration batch with a non-zero status; the daily
  runner logs it as non-fatal and retains the final site publish as recovery.

### Constraints and verification
* No models, providers, quality thresholds, credentials, or deployment endpoints
  change. No production restart or full pipeline run is authorized by this fix.
* Offline regressions must prove grader reuse, per-article publish ordering,
  failed-track rejection, hook failure propagation, and text-first deployment.
* Material unknowns: active production interpreter and model versions, current
  generation/grading timings, and end-to-end latency. Local mocked checks do not
  establish a measured production speedup.
