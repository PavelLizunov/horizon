---
layout: default
title: Narration (TeraTTSv2)
---

# Narration (TeraTTSv2)

Every published article gets a Russian voice track: the text is normalised, spoken
locally on the Mac, checked by a *different* model, encoded to Opus, uploaded to
object storage, and linked from the page.

- **Text preparation**: `src/ai/narration.py` — pure, no models, no network
- **Driver**: `scripts/dev_narrate_article.py` — runs on the Mac, in its own venv
- **Player**: one adaptive controller for phone and desktop, with the original
  native controls as its no-JavaScript/error fallback
  (`docs/assets/horizon-player.js`, CSS §17)
- **Tests**: `tests/test_narration.py` (offline)

The player uses one `<audio>` element for both its inline and sticky views.
Every screen gets the same transport controls (−10 seconds, play/pause, +15
seconds), a draggable progress range, elapsed/remaining time, and a native
speed selector. Browsers with the Popover API present it as a compact Horizon
button and accessible menu; browsers without Popover support keep the system
selector. The choice is remembered. Desktop alone adds volume: its speaker
opens a slider through hover, focus, or click, and the whole button-to-slider
area remains interactive while the pointer crosses it. Volume is deliberately
not remembered, so an old zero setting cannot produce moving progress with no
sound. Playback position is saved per article and resumes four seconds before
the saved point. The sticky view appears only after playback has started and
the inline player has scrolled above the viewport. On phones the inline card
uses a tighter reader-first rhythm and the sticky view omits duplicate time
labels; on desktop sticky is narrower, lighter, and less visually dominant.
Both enter with a short, reduced-motion-aware transition.

The source HTML still contains `<audio controls>`. JavaScript removes
`controls` only after both custom views mount; a script error, disabled
JavaScript, or an older browser therefore leaves a usable native player rather
than an empty gap.

## Pipeline

```
published page (docs/digest/<issue>/<slug>.md)
  └─ narration_text()   strip refs and URLs, expand numbers and dates
      └─ chunks()       120…700 characters, cut on sentence boundaries
          └─ TeraTTSv2  Russian voice, Tera-only pronunciation pass
              └─ whisper-large-v3-turbo  transcribe and grade
                  ├─ reached_the_end() ≥ 0.70  → keep
                  └─ speech_ends_at()          → trim the hallucinated tail
          └─ concat → Opus 24 kbit/s mono
              └─ check the join: duration, coverage, ending, tail
                  └─ R2, key <issue>/<slug>-<sha256[:10]>.opus
                      └─ attach_player() under the byline
```

## Mixed Russian and English pronunciation

`speakable()` stays engine-neutral. It strips page noise and expands numbers,
but preserves ordinary English words because both engines read many of them
better than a blanket transliteration. Immediately before Tera synthesis,
`tera_text()` applies a small measured pronunciation lexicon, says product IDs
as words, and separates Latin bases from Russian suffixes. The Qwen fallback
still receives the original spelling.

The current archive through 10 August 2026 contains 33 articles and 75,414
characters of narration. The reviewed lexicon has 161 entries and handles 503
observed occurrences. Another 213 unique Latin tokens (366 occurrences) remain
deliberately unchanged: they are mostly ordinary English, or names whose reading
was not trustworthy enough to guess. Examples from the current archive:

| Written | Given to Tera | Archive occurrences |
| --- | --- | ---: |
| OpenAI | Оупен Эй-Ай | 30 |
| GitHub | Гитхаб | 17 |
| Meta | Мета | 15 |
| Claude / Claude Code | Клод / Клод Код | 13 |
| Apple | Эпл | 11 |
| Sol | Сол | 10 |
| WeatherNext / OpenJDK / DeepSeek / Kubernetes | Уэзер Некст / Оупен джей-ди-кей / Дипсик / Кубернетес | 9 each |
| Oracle | Оракл | 8 |
| Databricks / PostgreSQL / HackerOne / Codex | Датабрикс / Постгрес-кью-эл / Хакер Уан / Кодекс | 7 each |
| Anthropic / Luna / ChatGPT | Антропик / Луна / Чат-джи-пи-ти | 6 each |

This is deliberately not an English-to-Russian transliterator. A direct A/B
check with the deployed `ru_f1` voice showed that adjacent `<en>` spans destroy
mixed speech (the checker heard only “одну одну одну”), while the lexicon made
previously distorted or omitted names recognisable. Unknown English remains
English until a real narration demonstrates that it needs an entry.

Every full issue preparation also rewrites
`data/pronunciation-candidates/<issue>.tsv`. It counts the Latin tokens that
still reach Tera after the current lexicon, so new names have one reviewable
backlog instead of being rediscovered by scanning the archive. The reports are
runtime state and are gitignored.

When `ai.pronunciation_model` names a separate cheap model, preparation also
sends that model the complete prepared text of the issue plus the candidate
counts. It asks for only names, brands, commands, abbreviations and uncommon
phrases that a Russian voice is likely to omit or distort. The response is
accepted only when the written phrase occurs in that issue, contains Latin,
and the proposed reading is Cyrillic without markup. Accepted readings are
stored in `data/pronunciation-reviews/<issue>.json` for review. Suggestions do
not reach Tera automatically: the cheap model can translate instead of
transcribing or confidently guess an unfamiliar brand. Only a manually reviewed
reading is promoted to the static Tera lexicon; Qwen remains unaffected.

The model is opt-in and never inherits `ai.model`: unset means skip, and naming
the primary model is refused. A malformed response or API failure is visible in
the narration log but falls back to the measured static lexicon, so a cheap
review cannot delay the readable site or remove audio. The production gateway
uses `deepseek-v4-flash-0731` with thinking disabled for this pass. Promote a
reviewed reading into `_TERA_PRONUNCIATIONS`; the per-issue JSON is the
review trail, not an unbounded source of global truth.

The original audit also found two English sections in the now-retired 4 August
legacy issue. That was an upstream content-language problem, not a pronunciation
problem; growing this lexicon to translate whole prose would hide the wrong
failure.

The finished file is checked again, because the pieces being individually sound
says nothing about the join. Four checks, cheapest first:

| Check | Catches |
| --- | --- |
| joined duration vs. sum of the pieces | a piece that never made it into the file — arithmetic, so it cannot be wrong |
| `coverage() ≥ 0.75` | a chunk lost with its audio |
| `reached_the_end() ≥ 0.70` | a file that stops before the article does |
| tail after `speech_ends_at()` ≤ 3 s | noise left after the last words |

## Why the checking model is a different model

Generation fails silently. It stops mid-sentence and pads the rest with noise, and
nothing about the returned audio says so — the file exists, the duration is
plausible, the beginning sounds fine. Only reading it back catches it, and the
generator cannot be the one to read it back: a model grading its own output prefers
its own output.

`whisper-large-v3-turbo` transcribes each chunk, and two measurements decide:

**`reached_the_end()`** — do the last words of the source appear in the transcript?
Only the tail words that occur *nowhere else* in the text count. Ordinary words
("в", "этом", "тут") were being matched against text the model had read minutes
earlier, which scored a reading that broke off halfway at 0.5, within reach of the
0.70 threshold.

Whole-text `coverage()` was tried first as the per-chunk gate and abandoned: a
recogniser mishearing two words in eighty costs more than truncation does, and on
complete takes the score topped out at 0.92 — it never separated good from broken.

It still runs once over the finished file, where it is answering a different
question: was a whole chunk lost in the join? That failure is worth twenty points
on a five-chunk article, so the threshold is 0.75. An earlier version used 0.9 and
flagged four sound files out of seven — the number was inside the noise floor of
the measurement it was thresholding.

**`speech_ends_at()`** — where does real speech stop? A hallucinated tail is a long
segment holding almost no text, so segments are judged by characters per second
(real speech runs about eleven; the cut-off is three). Anything past that point is
trimmed off whether or not the take passed.

## Chunk size is a correctness property

120–700 characters, and both ends were paid for:

- **Whole articles in one generation**: seven articles, one usable file. 86 % failure.
- **Two-word inputs**: nine characters produced eleven seconds of noise. Hence the
  floor, and hence headings are glued to their first sentence rather than spoken
  alone.

Sentences are packed into pieces of *even* length — `ceil(total / 700)` of them —
rather than filled to the ceiling one after another. Greedy filling plus a pass that
glued short leftovers on produced `[717, 773, 6]` on a real article: over the ceiling
twice, and a six-character piece sent to the model on its own, which is the exact
input the floor exists to prevent. Even division cannot produce either.

Three upstream reports describe the same behaviour from the other side, which is
the reason to treat the ceiling as a property rather than a preference:

| Report | Symptom |
| --- | --- |
| [mlx-audio #464](https://github.com/Blaizzy/mlx-audio/issues/464) | speech drops out of the middle of long generations |
| [QwenLM/Qwen3-TTS #239](https://github.com/QwenLM/Qwen3-TTS/issues/239) | speaking rate drifts over text longer than ~100 characters |
| [omlx #843](https://github.com/jundot/omlx/issues/843) | the token budget is silently capped |

The cap in #843 is real and present in the installed library
(`mlx_audio/tts/models/qwen3_tts/qwen3_tts.py`, `per_seq_max_tokens`), but it sits
on the `use_icl` branch — the voice-cloning path, which this pipeline does not use.
It would bite immediately if narration ever moved to a cloned voice.

## Other models, and why this one stayed

The intonation wanders and the reading speeds up toward the end. Both are what
an autoregressive sampler does, they are [QwenLM #239](https://github.com/QwenLM/Qwen3-TTS/issues/239),
and no setting on our side removes them. So the alternatives were tried. All of
them were rejected by ear, on the same article, and the reasons are recorded
here so the same ground is not covered twice.

| Tried | Outcome |
| --- | --- |
| Qwen3-TTS bf16, unquantised | identical faults — so quantisation was never the cause |
| Qwen3-TTS 25 Hz, which the technical report calls steadier on long text | **does not exist publicly** — no such model on HuggingFace, under any author |
| Shorter chunks (350), lower temperature (0.35) | measured: neither improved the rate spread, and 0.35 made it worse |
| Silero v5 | reads English badly. Its Russian model has no Latin graphemes at all and drops those words in silence; 13.5% of a digest is Latin. A transliteration layer was written and then reverted with it |
| Chatterbox Multilingual | no voice of its own, needs a reference clip; failed the end check outright (0.00); wrong stress and an accent |
| Marking stress in the text with ruaccent | Qwen has no stress of its own, so this looked promising. It is not: `+` marks are read aloud as the word "plus", and combining acutes garble the words into something unintelligible. The placer also errs on homographs by itself |

What that leaves is a model with livelier intonation than any alternative
tested, and two faults that belong to it rather than to this code. Bear them
rather than trade them for worse.

## Settings that were established by listening

| Setting | Value | Why |
| --- | --- | --- |
| `lang_code` | `"russian"` | The word, not `"ru"`. An ISO code is accepted and ignored, and the model then reads Cyrillic with Chinese phonetics. |
| Numbers | written out | Digits and words were compared on the same sentences; the written-out take is the one that sounds like a person. |
| Sampling | identical across retries | Varying `repetition_penalty` between attempts made the voice change character mid-article. |
| Bitrate | 24 kbit/s Opus | 16 was audibly worse on speech; 24 was not. |

## Things that bit, and what now stops them

| What happened | What prevents a repeat |
| --- | --- |
| Cleanup glob `{name}*.wav` deleted the kept best take | separate namespaces: `-gen*` for output, `-best` for what is kept |
| `immutable` cache headers on a reusable filename served stale audio | the object key carries a sha256 of the audio |
| R2 returned a 200 response truncated at 20480 bytes and the browser cached it | publishing refuses a short public copy; the player retries a stuck start with a fresh query |
| Re-narrating stacked a second player onto the page | `attach_player()` removes the old one, and is tested for stability |
| A page with no byline silently gained no player | `attach_player()` raises instead of returning unchanged |

## Running it

Two invocations, and they use **different interpreters** — this is the step that
wastes an afternoon if you get it wrong. Preparing the text needs the project's
dependencies; synthesising needs the Apple-Silicon-only ones, which are deliberately
not project dependencies.

```bash
ssh mm4 'zsh -lc "cd ~/horizon && .venv/bin/python scripts/dev_narrate_article.py --issue 2026-08-07-ru --write-all /tmp/narration"'
```

```bash
ssh mm4 'zsh -lc "cd ~/horizon && ~/tts/.venv/bin/python scripts/dev_narrate_article.py --speak-dir /tmp/narration --voice Serena --attach"'
```

`uv` is not on the PATH of a non-interactive ssh session on that box (it lives in
`~/bin`), so call the venv's python directly. `PATH` also needs `/opt/homebrew/bin`,
which the script prepends itself — `mlx_whisper` shells out to a bare `ffmpeg`.

An article whose verdict is not `ok` is **not uploaded and not linked**, and the run
exits non-zero. The audio stays in `~/tts/out/` so you can listen to what the check
objected to.

Credentials (`R2_*`, `NARRATION_PUBLIC_BASE`) live in `.env` on the Mac, written by
`scripts/setup_r2.py`, never in the repository — this repository is public.
