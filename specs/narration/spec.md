# Narration Specification

## 1. Objective
Generate high-quality Russian spoken voice tracks for all published digest articles using local neural text-to-speech synthesis (TeraTTSv2 / `ru_f1`), with Whisper-based independent grading, customized pronunciation lexicons, and zero-stall web publishing.

---

## 2. Requirements

### 2.1 Text Preparation
* Pure Python module `src/ai/narration.py`.
* Strip Markdown syntax, URLs, citations, code fences, and parenthetical artifacts.
* Unspell tech acronyms phonetically by letter name (*«GPU»* → *«джи-пи-ю»*).
* Apply vetted static pronunciation lexicon (`data/pronunciation_lexicon.json`).
* Segment text into balanced chunks strictly within 120–400 characters.

### 2.2 Synthesis & Independent Grading
* Engine: TeraTTSv2 (`ru_f1` voice).
* Isolated execution in dedicated venv (`~/tts/.venv`).
* Grade synthesis piece-by-piece using Whisper ASR against source chunk text.
* Uncorroborated or defective audio is rejected and never published.

### 2.3 Audio Delivery
* Encode audio at 1.25x tempo with ffmpeg.
* Upload MP3 to Cloudflare R2 bucket or direct Caddy static storage.
* Attach accessible custom HTML5 audio player to MkDocs article pages.
