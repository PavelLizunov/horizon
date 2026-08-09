"""Narrate archived articles, verify what came out, and attach it to the pages.

Prepared text comes from `src/ai/narration.py`, which is tested; this script is
the driver. Text preparation and synthesis run in different environments —
mlx-audio brings a heavy dependency tree that has no business in the project
venv — so the two halves are separate invocations:

    uv run python scripts/dev_narrate_article.py --issue <id> --write-all /tmp/narration
    ~/tts/.venv/bin/python scripts/dev_narrate_article.py \\
        --speak-dir /tmp/narration --voice Serena --attach

Everything here is the residue of something that went wrong and was measured:

  * `lang_code` takes the model's own names ("russian"), not ISO codes. An
    unrecognised value is ignored silently and Cyrillic gets read with Chinese
    phonetics.
  * `max_tokens` defaults to 1200, which at the codec's 12.5 Hz is a hard
    ceiling of 96 seconds. Past it the model does not stop cleanly, it runs to
    the cap and fills the tail with noise.
  * the model's own `speed` made output *longer*, not faster — 50.6s against
    27.1s for the same text. Playback rate belongs in the player.
  * long generations are unreliable. Narrating a whole issue in one take each,
    then transcribing the results, showed one clean file in seven: coverage
    ran 0.57 to 0.89, with up to 72 seconds of babble at the end. The only
    clean one was also the shortest. So text is split, and every piece is
    checked.
  * duration is not a check. The worst file measured 204 seconds against 237
    expected — well inside any sane tolerance, and broken. What works is
    recognising the audio and comparing the words: a second model grading the
    first, rather than the generator judging itself.
"""

import argparse
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# mlx_whisper shells out to a bare `ffmpeg`, and a non-interactive ssh session
# on this box has almost no PATH.
os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")

MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit"
CHECKER = "mlx-community/whisper-large-v3-turbo"
LANGUAGE = "russian"
CODEC_HZ = 12.5
SECONDS_PER_CHAR = 1 / 11.5  # measured on this voice reading this digest

# Splitting lives in src/ai/narration.py, with the sizes and the reasoning; it
# is text handling, and text handling is tested.

# The gate is "did the reading reach the end", not "how many words match".
# Whole-word coverage measured the wrong thing on short pieces: complete takes
# topped out at 0.92 because a couple of misheard words cost more than
# truncation did. Against the tail, a complete take scores 1.0, one misheard
# word 0.9, and a truncated one 0.4 — so 0.7 separates them with room to spare.
MIN_TAIL = 0.7
ATTEMPTS = 3

# "Consistent" preset from the model's generation-parameter documentation, and
# identical for every chunk including retries. Varying it per chunk is what
# made an earlier attempt wander between a whisper and a shout.
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
ENV_PATH = REPO / ".env"




def _ffmpeg(*arguments: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *arguments], check=True)


def _duration(path: Path) -> float:
    with wave.open(str(path)) as handle:
        return handle.getnframes() / handle.getframerate()


def _upload(audio: Path, issue: str, slug: str) -> str:
    """Put the file in object storage and return the URL the page should use.

    Raises rather than falling back to a local copy: a half-configured setup
    that quietly wrote to disk would look like it worked and fill the disk.
    """
    import boto3
    from botocore.client import Config
    from dotenv import load_dotenv

    load_dotenv(ENV_PATH)
    missing = [
        name
        for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY", "R2_SECRET_KEY", "R2_BUCKET",
                     "NARRATION_PUBLIC_BASE")
        if not os.environ.get(name)
    ]
    if missing:
        raise SystemExit(
            "object storage is not configured: missing "
            + ", ".join(missing)
            + "\nRun scripts/setup_r2.py first."
        )

    from src.ai.narration import audio_key

    key = audio_key(issue, slug, audio.read_bytes())
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY"],
        aws_secret_access_key=os.environ["R2_SECRET_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )
    client.upload_file(
        str(audio), os.environ["R2_BUCKET"], key,
        ExtraArgs={"ContentType": "audio/ogg"},
    )
    return f"{os.environ['NARRATION_PUBLIC_BASE'].rstrip('/')}/{key}"


def _attach(issue: str, slug: str, url: str, seconds: float) -> None:
    """Put a player into the published page, pointing at the uploaded audio.

    Upload first, edit the page second, both after publishing: a page linking
    to audio that failed to upload is worse than a page with no player. The
    player sits under the byline — the choice to listen instead of read is made
    before reading, not after.
    """
    page = SITE_DIGEST_DIR / issue / f"{slug}.md"
    if not page.exists():
        print(f"  no published page at {page}", file=sys.stderr)
        return

    from src.ai.narration import attach_player

    try:
        updated = attach_player(page.read_text(encoding="utf-8"), url, seconds)
    except ValueError as error:
        print(f"  {error}; player not inserted", file=sys.stderr)
        return
    page.write_text(updated, encoding="utf-8")


def _listen(audio: Path, out: Path, checker) -> dict:
    """Transcribe a finished file, and say where its speech actually stops."""
    import mlx_whisper

    from src.ai.narration import speech_ends_at

    probe = out / "listen-probe.wav"
    _ffmpeg("-i", str(audio), "-ac", "1", "-ar", "16000", str(probe))
    result = mlx_whisper.transcribe(
        str(probe), path_or_hf_repo=checker, language="ru", verbose=False
    )
    probe.unlink(missing_ok=True)

    return {
        "text": result.get("text", ""),
        "speech_end": speech_ends_at(result.get("segments", [])),
    }


def _speak_chunk(text: str, out: Path, name: str, voice: str, model, checker) -> Path | None:
    """One chunk, synthesised until a transcript says it is all there.

    The check is the whole point. Generation fails silently and often: it stops
    mid-sentence and pads with noise, and nothing about the returned audio says
    so. Only reading it back does.
    """
    from mlx_audio.tts.generate import generate_audio
    import mlx_whisper

    from src.ai.narration import reached_the_end, speech_ends_at

    budget = int(len(text) * SECONDS_PER_CHAR * CODEC_HZ * 1.8) + 200
    raw = out / f"{name}-raw.wav"
    best: tuple[float, Path] | None = None

    for attempt in range(1, ATTEMPTS + 1):
        # Only the generator's own output is cleared. An earlier version wiped
        # `{name}*.wav`, which also deleted the kept best take from the previous
        # attempt and left the concat step pointing at a file that no longer
        # existed.
        for stale in out.glob(f"{name}-gen*.wav"):
            stale.unlink()
        generate_audio(
            text=text, model=model, voice=voice, lang_code=LANGUAGE,
            max_tokens=budget, output_path=str(out), file_prefix=f"{name}-gen",
            audio_format="wav", join_audio=True, verbose=False,
            instruct=INSTRUCT, **STEADY,
        )
        produced = sorted(out.glob(f"{name}-gen*.wav"))
        if not produced:
            continue
        produced[0].replace(raw)

        probe = out / f"{name}-probe.wav"
        _ffmpeg("-i", str(raw), "-ac", "1", "-ar", "16000", str(probe))
        result = mlx_whisper.transcribe(
            str(probe), path_or_hf_repo=checker, language="ru", verbose=False
        )
        probe.unlink(missing_ok=True)

        score = reached_the_end(text, result.get("text", ""))
        # Trim to where speech actually stops: that removes trailing babble
        # whether or not the take is otherwise good.
        speech_end = speech_ends_at(result.get("segments", []))

        take = out / f"{name}-take.wav"
        take.unlink(missing_ok=True)
        if speech_end > 0 and _duration(raw) - speech_end > 1.5:
            _ffmpeg("-i", str(raw), "-t", f"{speech_end + 0.4:.2f}", "-c", "copy", str(take))
        else:
            raw.replace(take)
        raw.unlink(missing_ok=True)

        if best is None or score > best[0]:
            if best is not None:
                best[1].unlink(missing_ok=True)
            kept = out / f"{name}-best.wav"
            kept.unlink(missing_ok=True)
            take.replace(kept)
            best = (score, kept)
        else:
            take.unlink(missing_ok=True)

        if score >= MIN_TAIL:
            return best[1]
        print(f"    reached {score:.2f} of the end, retry {attempt}/{ATTEMPTS}", flush=True)

    if best is not None:
        print(f"    best {best[0]:.2f} after {ATTEMPTS} attempts", file=sys.stderr)
        return best[1]
    return None


def _speak(text: str, issue: str, slug: str, args, model, checker) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    prefix = f"{issue}-{slug}"
    for stale in out.glob(f"{prefix}*"):
        stale.unlink()

    from src.ai.narration import chunks

    pieces = chunks(text)
    parts: list[Path] = []
    started = time.time()
    for index, piece in enumerate(pieces):
        rendered = _speak_chunk(
            piece, out, f"{prefix}-p{index:02d}", args.voice, model, checker
        )
        if rendered is None:
            print(f"  chunk {index} produced nothing", file=sys.stderr)
            return 1
        parts.append(rendered)
    synth = time.time() - started

    listing = out / f"{prefix}.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    joined = out / f"{prefix}.wav"
    expected = sum(_duration(part) for part in parts)
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined))
    for part in parts:
        part.unlink()
    listing.unlink()

    seconds = _duration(joined)
    target = out / f"{prefix}.opus"
    _ffmpeg(
        "-i", str(joined), "-ac", "1", "-ar", "24000", "-c:a", "libopus",
        "-b:a", args.bitrate, "-application", "audio", "-vbr", "on",
        "-compression_level", "10", str(target),
    )
    joined.unlink()

    # Verify the finished article, not only its pieces. Each chunk was already
    # checked against its own text, so what is left to catch here is the join:
    # a piece lost on the way into the file, and anything after the last words.
    whole = _listen(target, out, checker)
    from src.ai.narration import coverage, reached_the_end

    score = coverage(text, whole["text"])
    ending = reached_the_end(text, whole["text"])
    tail = max(0.0, seconds - whole["speech_end"])
    lost = expected - seconds

    verdict = "ok"
    # Arithmetic first, because it cannot be wrong: the finished file is as long
    # as the pieces that went into it, or a piece did not go in.
    if lost > 0.5:
        verdict = f"JOIN LOST {lost:.0f}s"
    # Then the transcript. The threshold is 0.75, not the 0.9 an earlier version
    # used: whole-file coverage tops out around 0.92 on takes that are perfectly
    # complete, because a recogniser mishears, so 0.9 flagged four sound files
    # out of seven. A genuinely missing chunk costs far more than mishearing —
    # one piece in five is twenty points — and 0.75 tells those apart.
    elif score < 0.75:
        verdict = "TEXT MISSING"
    elif ending < 0.7:
        verdict = "ENDING MISSING"
    elif tail > 3:
        verdict = f"{tail:.0f}s TAIL"
    print(
        f"  {len(pieces)} chunks, {seconds / 60:.1f} min, {synth:.0f}s wall, "
        f"{target.stat().st_size / 1024:.0f} KB, "
        f"coverage {score:.2f}, ending {ending:.2f}  {verdict}",
        flush=True,
    )
    # A failed check must not reach the site. An earlier version printed the
    # verdict, published anyway, and returned 0, so a run that had just measured
    # its own output as broken still reported "7/7 narrated" — the checking was
    # real and nothing acted on it. The audio stays on disk for listening to.
    if verdict != "ok":
        print(f"  {issue}/{slug}: {verdict}, not published", file=sys.stderr)
        return 1

    if args.attach:
        url = _upload(target, issue, slug)
        _attach(issue, slug, url, seconds)
        print(f"  {url}", flush=True)
    return 0


def _speak_many(directory: Path, args) -> int:
    """Every prepared text in a directory, one model load for the lot."""
    from mlx_audio.tts.utils import load_model

    texts = sorted(directory.glob("*.txt"))
    if not texts:
        print(f"no prepared texts in {directory}", file=sys.stderr)
        return 1

    print(f"loading {MODEL.split('/')[-1]} and {CHECKER.split('/')[-1]} …", flush=True)
    model = load_model(model_path=MODEL)

    failures = []
    started = time.time()
    for index, text_file in enumerate(texts, start=1):
        issue, _, slug = text_file.stem.partition("__")
        print(f"\n[{index}/{len(texts)}] {issue} {slug}", flush=True)
        try:
            if _speak(text_file.read_text(encoding="utf-8"), issue, slug, args,
                      model, CHECKER):
                failures.append(f"{issue}/{slug}")
        except Exception as error:  # noqa: BLE001 — one bad article must not end the run
            print(f"  FAILED {type(error).__name__}: {error}", file=sys.stderr)
            failures.append(f"{issue}/{slug}")

    print(
        f"\n{len(texts) - len(failures)}/{len(texts)} narrated in "
        f"{(time.time() - started) / 60:.0f} min"
    )
    if failures:
        print("failed: " + ", ".join(failures), file=sys.stderr)
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", default="2026-08-07-ru")
    parser.add_argument("--slug", default="tech-news-1")
    parser.add_argument("--voice", default="Serena")
    parser.add_argument("--bitrate", default="24k")
    parser.add_argument("--out", default=str(Path.home() / "tts" / "out"))
    parser.add_argument("--write-all", help="write every article of the issue here")
    parser.add_argument("--speak-dir", help="synthesise every prepared text here")
    parser.add_argument("--attach", action="store_true", help="upload and link it")
    args = parser.parse_args()

    if args.speak_dir:
        return _speak_many(Path(args.speak_dir), args)

    # Imported here, not at module scope: the archive parser drags in the
    # project's dependencies, and synthesis runs from a venv without them.
    from scripts.dev_reindex_archive import SUMMARIES_DIR, parse_summary
    from src.ai.narration import chunks, narration_text

    date, _, language = args.issue.rpartition("-")
    summary = SUMMARIES_DIR / f"horizon-{date}-{language}.md"
    if not summary.exists():
        print(f"no such issue: {summary}", file=sys.stderr)
        return 1

    documents = parse_summary(summary.read_text(encoding="utf-8"), date, language)
    target = Path(args.write_all or ".")
    target.mkdir(parents=True, exist_ok=True)
    total = 0
    for document in documents:
        slug = document["id"].removeprefix(f"{date}-{language}-")
        if not args.write_all and slug != args.slug:
            continue
        text = narration_text(
            document["title"], document["lead"], document["blocks"], date=date
        )
        total += len(text)
        (target / f"{args.issue}__{slug}.txt").write_text(text, encoding="utf-8")
        print(
            f"{args.issue}__{slug}.txt  {len(text):>5} chars  "
            f"{len(chunks(text))} chunks  ~{len(text) * SECONDS_PER_CHAR / 60:.1f} min"
        )
    print(f"\n~{total * SECONDS_PER_CHAR / 60:.0f} min of speech to synthesise")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
