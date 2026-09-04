import io
import os
import subprocess
import tarfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "horizon-static-publish"


def _env(tmp_path, command=""):
    site = tmp_path / "site"
    audio = tmp_path / "audio"
    site.mkdir()
    audio.mkdir()
    return {
        **os.environ,
        "HORIZON_PUBLISH_CONFIG": str(tmp_path / "missing.env"),
        "HORIZON_SITE_ROOT": str(site),
        "HORIZON_AUDIO_ROOT": str(audio),
        "HORIZON_AUDIO_MAX_BYTES": "1000",
        "HORIZON_MAX_OPUS_BYTES": "100",
        "SSH_ORIGINAL_COMMAND": command,
    }, site, audio


def _site_archive():
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as archive:
        content = b"new site"
        info = tarfile.TarInfo("index.html")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return payload.getvalue()


def test_legacy_site_publish_still_accepts_the_existing_command(tmp_path):
    env, site, _ = _env(tmp_path, "rm -rf old && tar xzf - -C live")
    (site / "old.html").write_text("old", encoding="utf-8")

    result = subprocess.run(
        ["sh", str(SCRIPT)], input=_site_archive(), env=env, check=False
    )

    assert result.returncode == 0
    assert (site / "index.html").read_bytes() == b"new site"
    assert not (site / "old.html").exists()


def test_opus_publish_validates_and_writes_atomically(tmp_path):
    key = "2026-09-04-ru/tech-news-1-1234567890.opus"
    env, _, audio = _env(
        tmp_path, f"put-opus {tmp_path / 'audio'} {key} 9 1000"
    )

    result = subprocess.run(
        ["sh", str(SCRIPT)], input=b"OggSaudio", env=env, check=False
    )

    published = audio / key
    assert result.returncode == 0
    assert published.read_bytes() == b"OggSaudio"
    assert published.stat().st_mode & 0o777 == 0o644
    assert not list(audio.glob(".upload.*"))


def test_opus_publish_rejects_traversal_wrong_root_and_non_ogg(tmp_path):
    good_key = "2026-09-04-ru/tech-news-1-1234567890.opus"
    for kind in ("traversal", "wrong-root", "non-ogg"):
        case = tmp_path / kind
        case.mkdir()
        expected_root = case / "audio"
        key = "../outside.opus" if kind == "traversal" else good_key
        requested_root = case / "elsewhere" if kind == "wrong-root" else expected_root
        payload = b"not-audio" if kind == "non-ogg" else b"OggSaudio"
        env, _, audio = _env(
            case, f"put-opus {requested_root} {key} {len(payload)} 1000"
        )

        result = subprocess.run(
            ["sh", str(SCRIPT)], input=payload, env=env, check=False
        )

        assert result.returncode != 0
        assert not list(audio.rglob("*.opus"))
        assert not list(audio.glob(".upload.*"))
