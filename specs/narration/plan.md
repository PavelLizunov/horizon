# Narration Architecture Plan

## 1. Decoupled Two-Phase Publish
1. **Phase 1 (Immediate Text Publish)**: `run-daily.sh` builds and ships text markdown pages to ingress immediately after LLM enrichment.
2. **Phase 2 (Post-publish Narration)**: `run-daily.sh` invokes `scripts/dev_narrate_article.py` synchronously for the issue. The script synthesizes audio in the isolated narration interpreter, verifies Whisper transcript match, uploads Opus (`.opus`) audio, and updates page metadata. An optional `--after-attach` argv hook runs the same daily script in ship-only/no-pull mode after each successfully attached article, before the next synthesis. The shell retains a final site publish as recovery after narration failures.
3. **Grader lifetime**: A lazy cached loader holds the Linux `faster_whisper.WhisperModel(checker, device='cpu', compute_type='int8')` result for the narration process. Chunk and final-file transcription reuse it with unchanged options; macOS `mlx_whisper` behavior is untouched.
4. **Hook contract and safety**: Parse trailing argv with `argparse.REMAINDER` (including command flags); require a non-empty command and `--speak-dir --attach`. Execute with `subprocess.run(..., check=True)` without `shell=True`. Never derive commands from article content. Hook failures are reported and return non-zero before the next article; failed grading never invokes the hook.
5. **Verification**: Mock model loading, synthesis, upload, and the hook to prove load-once behavior, unchanged grader options, first attach/publish before second synthesis, rejected-track suppression, and publish-error propagation. Run deployment-order tests and the full offline pytest suite. No production timing claims follow from mocked execution.

## 2. Invariants
* Grader model (Whisper) is independent of generator (TeraTTSv2).
* Chunk sizes strictly enforced (120–400 chars).
* Player default speed is 1.0x on a 1.25x pre-encoded stream.
