"""Narrate one archived article, encode it to Opus and attach it to the page.

A trial of the full shape before it becomes a pipeline stage: prepare the text,
speak it, encode it, drop the file next to the article and put a player in the
page. Prepared text comes from `src/ai/narration.py`, which is tested; this
script is only the driver.

Text preparation and synthesis run in different environments — mlx-audio brings
its own heavy dependency tree and has no business in the project venv — so the
two halves are separate invocations:

    uv run python scripts/dev_narrate_article.py --write /tmp/narration.txt
    ~/tts/.venv/bin/python scripts/dev_narrate_article.py \\
        --speak /tmp/narration.txt --voice Serena --attach

Findings that shaped the settings, all measured rather than assumed:

  * `lang_code` takes the model's own names ("russian"), not ISO codes. An
    unrecognised value is ignored silently and the model reads Cyrillic with
    Chinese phonetics.
  * the default `max_tokens=1200` is a hard ceiling of 96 seconds at the codec's
    12.5 Hz. Text past it does not truncate cleanly; the model runs to the cap
    and fills the tail with noise.
  * one generation for the whole article, never chunk-and-join. Chunking was
    only ever a way round that ceiling, and stitching independent generations
    made the delivery wander between a whisper and a shout.
  * the model's own `speed` made output *longer*, not faster — 50.6s against
    27.1s for the same text. Playback rate belongs in the player.
"""

import argparse
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit"
LANGUAGE = "russian"
CODEC_HZ = 12.5
SECONDS_PER_CHAR = 1 / 11.5  # measured on this voice reading this digest
OVERRUN_RATIO = 1.7
# Failures are intermittent, so a retry is worth more than any parameter
# tuning. Three is where it stops being worth waiting for.
ATTEMPTS = 3

# "Consistent" preset from the model's generation-parameter documentation.
# Narration wants faithful delivery; the sampling defaults are tuned for variety.
STEADY = {
    "temperature": 0.7,
    "top_k": 30,
    "top_p": 0.85,
    "repetition_penalty": 1.15,
}

INSTRUCT = (
    "Ровный дикторский тон. Спокойно, размеренно, без эмоциональных перепадов, "
    "одинаковая громкость от начала до конца."
)

SITE_DIGEST_DIR = REPO / "docs" / "digest"


def _ffmpeg() -> str:
    """Absolute path when needed: a non-interactive ssh session on the box gets
    almost no PATH, so a bare "ffmpeg" is not found."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if Path(candidate).exists():
            return candidate
    raise SystemExit("ffmpeg not found; brew install ffmpeg")


def _attach(issue: str, slug: str, audio: Path, seconds: float) -> None:
    """Put the file beside the article and a player inside it.

    Deliberately after publishing rather than during: if synthesis fails the
    page is simply a page, instead of a page pointing at audio that does not
    exist. The player goes right under the byline — the decision to listen
    instead of read is made before reading, not after.
    """
    issue_dir = SITE_DIGEST_DIR / issue
    page = issue_dir / f"{slug}.md"
    if not page.exists():
        print(f"no published page at {page}; skipping attach", file=sys.stderr)
        return

    shutil.copy2(audio, issue_dir / audio.name)
    markdown = page.read_text(encoding="utf-8")
    if 'class="hz-narration"' in markdown:
        markdown = "\n".join(
            line for line in markdown.split("\n") if "hz-narration" not in line
        )

    minutes = max(1, round(seconds / 60))
    player = (
        f'<audio class="hz-narration" controls preload="none" '
        f'src="../{audio.name}" '
        f'aria-label="Озвучка статьи, {minutes} мин"></audio>'
    )
    index = markdown.find('<p class="hz-byline">')
    if index == -1:
        print("no byline found; player not inserted", file=sys.stderr)
        return
    end = markdown.index("</p>", index) + len("</p>")
    page.write_text(markdown[:end] + "\n\n" + player + markdown[end:], encoding="utf-8")
    print(f"attached   {issue_dir / audio.name}")
    print(f"page       {page}")


def _speak(text: str, args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    prefix = f"{args.issue}-{args.slug}-{args.voice}"
    for stale in out.glob(f"{prefix}*"):
        stale.unlink()

    from mlx_audio.tts.generate import generate_audio

    expected = len(text) * SECONDS_PER_CHAR
    budget = int(expected * CODEC_HZ * 2.0) + 400

    # Both directions are failures, and both are intermittent — the same text
    # read correctly once and lost 40% of itself the next time. Too long means
    # the model never stopped and the tail is noise; too short means it silently
    # dropped content, which is the dangerous one: the speech stays fluent and
    # only a comparison against the text reveals the hole. Since the whole
    # article is a single take, a retry costs one generation and there is no
    # consistency to lose.
    synth = 0.0
    source = None
    seconds = 0.0
    for attempt in range(1, ATTEMPTS + 1):
        for stale in out.glob(f"{prefix}*.wav"):
            stale.unlink()
        started = time.time()
        generate_audio(
            text=text,
            model=MODEL,
            voice=args.voice,
            lang_code=LANGUAGE,
            max_tokens=budget,
            output_path=str(out),
            file_prefix=prefix,
            audio_format="wav",
            join_audio=True,
            verbose=False,
            instruct=INSTRUCT,
            **STEADY,
        )
        synth += time.time() - started

        wavs = sorted(out.glob(f"{prefix}*.wav"))
        if not wavs:
            print("no audio produced", file=sys.stderr)
            return 1
        source = wavs[0]
        with wave.open(str(source)) as handle:
            seconds = handle.getnframes() / handle.getframerate()

        if expected * 0.7 <= seconds <= expected * OVERRUN_RATIO:
            break
        fault = "ran past the end" if seconds > expected else "dropped text"
        if attempt < ATTEMPTS:
            print(
                f"  attempt {attempt}: {seconds:.0f}s for ~{expected:.0f}s "
                f"({fault}) — retrying",
                flush=True,
            )
        else:
            print(
                f"warning: {seconds:.0f}s of audio for ~{expected:.0f}s of text "
                f"after {ATTEMPTS} attempts ({fault}) — not attaching",
                file=sys.stderr,
            )
            return 1

    target = out / f"{prefix}.opus"
    encode = subprocess.run(
        [
            _ffmpeg(), "-y", "-loglevel", "error",
            "-i", str(source),
            "-ac", "1", "-ar", "24000",
            "-c:a", "libopus", "-b:a", args.bitrate,
            "-application", "audio", "-vbr", "on", "-compression_level", "10",
            str(target),
        ],
        capture_output=True,
        text=True,
    )
    if encode.returncode != 0:
        print(encode.stderr, file=sys.stderr)
        return 1
    source.unlink()

    print(f"audio      {seconds / 60:.1f} min ({seconds:.0f} s)")
    print(f"synthesis  {synth:.0f} s wall -> {seconds / synth:.1f}x realtime")
    print(
        f"opus       {target.stat().st_size / 1024:.0f} KB at {args.bitrate} "
        f"({target.stat().st_size / 1024 / (seconds / 60):.0f} KB per minute)"
    )

    if args.attach:
        named = target.with_name(f"{args.slug}.opus")
        target.replace(named)
        _attach(args.issue, args.slug, named, seconds)
    else:
        print(f"file       {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", default="2026-08-07-ru")
    parser.add_argument("--slug", default="tech-news-1")
    parser.add_argument("--voice", default="Serena")
    parser.add_argument("--bitrate", default="24k", help="Opus target, e.g. 16k")
    parser.add_argument(
        "--out", default=str(Path.home() / "tts" / "out"), help="working directory"
    )
    parser.add_argument("--write", help="write the narration text here and stop")
    parser.add_argument("--speak", help="synthesise a prepared text file")
    parser.add_argument(
        "--attach", action="store_true", help="copy the audio beside the article"
    )
    args = parser.parse_args()

    if args.speak:
        return _speak(Path(args.speak).read_text(encoding="utf-8"), args)

    # Imported here, not at module scope: the archive parser drags in the
    # project's dependencies, and synthesis runs from a venv that has only
    # mlx-audio.
    from scripts.dev_reindex_archive import SUMMARIES_DIR, parse_summary
    from src.ai.narration import narration_text

    date, _, language = args.issue.rpartition("-")
    summary = SUMMARIES_DIR / f"horizon-{date}-{language}.md"
    if not summary.exists():
        print(f"no such issue: {summary}", file=sys.stderr)
        return 1

    documents = parse_summary(summary.read_text(encoding="utf-8"), date, language)
    wanted = f"{date}-{language}-{args.slug}"
    document = next((d for d in documents if d["id"] == wanted), None)
    if document is None:
        print(f"no such article: {wanted}", file=sys.stderr)
        print("available:", [d["id"] for d in documents], file=sys.stderr)
        return 1

    text = narration_text(
        document["title"], document["lead"], document["blocks"], date=date
    )
    print(f"--- narration text, {len(text)} chars ---")
    print(text)
    if args.write:
        Path(args.write).write_text(text, encoding="utf-8")
        print(f"written to {args.write}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
