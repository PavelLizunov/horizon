# Narration Tasks & Implementation Checklist

- [x] Implement text cleaner, chunker, and acronym unspeller (`src/ai/narration.py`).
- [x] Build isolated synthesis driver for TeraTTSv2 and Whisper grading (`scripts/dev_narrate_article.py`).
- [x] Create vetted Russian pronunciation lexicon for tech terminology (`_TERA_PRONUNCIATIONS` in `src/ai/narration.py`).
- [x] Implement accessible responsive HTML5 audio player for desktop and mobile.
- [x] Integrate two-phase build/ship in deployment script (`deploy/run-daily.sh`).
- [x] Document audio measurements and benchmarking in `docs/narration.md`.

## Player Availability Fix

- [ ] Cache the Linux Whisper grader without changing transcription options.
- [ ] Add the optional argv-based after-attach hook and daily ship-only wiring.
- [ ] Verify per-article ordering and failure boundaries with offline regressions.
- [ ] Update narration/deployment documentation and local guides.
- [ ] Run the full offline suite and review the task diff.
- [ ] Commit verified changes and push the dedicated task branch.

### Verification record

- Red: the new regression module failed on repeated grader loads and missing
  per-article hooks before implementation; all external calls were mocked.
- Green: `.venv/bin/pytest -ra` — 862 passed; shell integration uses isolated
  pipeline, narrator, MkDocs, and SSH stubs and confirms text-first publication,
  per-article refreshes, and no recursive pipeline/narration.
- `bash -n deploy/run-daily.sh`, Python compilation, and `git diff --check` passed.
- In-session diff review: hook argv is operator-owned, executed without a shell;
  article content never selects commands. Existing quality thresholds are intact.
- Limits: zsh is unavailable locally, so shell integration used bash-compatible
  syntax with a zsh shim. No production deployment, real audio run, or latency
  measurement was performed. No authorized explicit-model independent reviewer
  route was available; review was performed in-session.
- Deployment handoff: this task branch is not merged to main. The daily runner
  pulls main by default; its production behavior does not change until the
  verified code is integrated/deployed. Rebuild/transfer remains whole-site and
  remote replacement remains non-atomic.
