"""Offline checks for grader reuse and per-article player publication."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import dev_narrate_article as driver


def test_linux_whisper_is_loaded_once_per_checker(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    grader = Mock()
    segment = SimpleNamespace(start=0.0, end=1.0, text="готово", words=[])
    grader.transcribe.side_effect = lambda *a, **kw: (iter([segment]), None)
    load_model = Mock(return_value=grader)
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=load_model))
    loader = getattr(driver, "_load_whisper", None)
    if loader is not None:
        loader.cache_clear()
    try:
        for name in ("turbo", "turbo", "large", "large"):
            assert driver._transcribe(tmp_path / "piece.wav", name)["text"] == "готово"
        assert load_model.call_count == 2
        assert [call.args for call in load_model.call_args_list] == [("turbo",), ("large",)]
        assert all(call.kwargs == {"device": "cpu", "compute_type": "int8"}
                   for call in load_model.call_args_list)
        for call in grader.transcribe.call_args_list:
            assert call.kwargs == {"language": "ru"}
    finally:
        if loader is not None:
            loader.cache_clear()


def _mock_batch(monkeypatch, tmp_path, outcomes):
    events = []
    for slug in ("first", "second"):
        (tmp_path / f"issue__{slug}.txt").write_text("Текст", encoding="utf-8")

    monkeypatch.setenv("TERATTS_URL", "http://tts.invalid")

    def speak(text, issue, slug, args, model, checker):
        stem = f"{issue}__{slug}"
        events.append(("speak", stem))
        if outcomes[stem]:
            # _speak's success contract includes verified upload and attachment.
            events.append(("attach", stem))
            return 0
        return 1

    def publish(argv, check):
        assert argv == ["publisher", "argument with spaces", "--flag"]
        assert check is True
        events.append(("publish", events[-1][1]))

    monkeypatch.setattr(driver, "_speak", speak)
    monkeypatch.setattr(driver.subprocess, "run", publish)
    monkeypatch.setattr(sys, "argv", [
        "narrate", "--speak-dir", str(tmp_path), "--attach",
        "--after-attach", "publisher", "argument with spaces", "--flag",
    ])
    return events


def test_each_player_publishes_before_next_article(monkeypatch, tmp_path):
    events = _mock_batch(monkeypatch, tmp_path, {"issue__first": True, "issue__second": True})
    assert driver.main() == 0
    assert events == [
        ("speak", "issue__first"), ("attach", "issue__first"), ("publish", "issue__first"),
        ("speak", "issue__second"), ("attach", "issue__second"), ("publish", "issue__second"),
    ]


def test_rejected_track_does_not_publish_player(monkeypatch, tmp_path):
    events = _mock_batch(monkeypatch, tmp_path, {"issue__first": False, "issue__second": True})
    assert driver.main() == 1
    assert events == [
        ("speak", "issue__first"), ("speak", "issue__first"),
        ("speak", "issue__second"), ("attach", "issue__second"), ("publish", "issue__second"),
    ]


@pytest.mark.parametrize("error", [driver.subprocess.CalledProcessError(1, "publisher"), OSError("missing publisher")])
def test_publish_failure_stops_batch(monkeypatch, tmp_path, error):
    events = _mock_batch(monkeypatch, tmp_path, {"issue__first": True, "issue__second": True})

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(driver.subprocess, "run", fail)
    assert driver.main() == 1
    assert events == [("speak", "issue__first"), ("attach", "issue__first")]


@pytest.mark.parametrize("arguments", [[], ["--speak-dir", "scratch"]])
def test_after_attach_requires_attached_batch(monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", ["narrate", *arguments, "--after-attach", "publisher"])
    with pytest.raises(SystemExit) as exc:
        driver.main()
    assert exc.value.code == 2


def test_existing_batch_invocation_needs_no_hook(monkeypatch, tmp_path):
    events = _mock_batch(monkeypatch, tmp_path, {"issue__first": True, "issue__second": True})
    monkeypatch.setattr(sys, "argv", ["narrate", "--speak-dir", str(tmp_path), "--attach"])
    assert driver.main() == 0
    assert not any(event[0] == "publish" for event in events)


def test_after_attach_requires_nonempty_command(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "narrate", "--speak-dir", "scratch", "--attach", "--after-attach",
    ])
    with pytest.raises(SystemExit) as exc:
        driver.main()
    assert exc.value.code == 2


@pytest.mark.parametrize("content", [None, "Статья без маркера проверки."])
def test_attachment_failure_is_not_reported_as_success(monkeypatch, tmp_path, content):
    monkeypatch.setattr(driver, "SITE_DIGEST_DIR", tmp_path / "docs" / "digest")
    page = tmp_path / "docs" / "digest" / "issue" / "article.md"
    if content is not None:
        page.parent.mkdir(parents=True)
        page.write_text(content, encoding="utf-8")
    with pytest.raises(RuntimeError):
        driver._attach("issue", "article", "https://audio.invalid/track.opus", 12.0)
    if content is not None:
        assert page.read_text(encoding="utf-8") == content


def test_grader_repo_alias_reuses_same_model(monkeypatch, tmp_path):
    grader = Mock()
    grader.transcribe.side_effect = lambda *a, **kw: (iter([]), None)
    load_model = Mock(return_value=grader)
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=load_model))
    monkeypatch.setenv("WHISPER_MODEL", "turbo")
    driver._load_whisper.cache_clear()
    try:
        driver._transcribe(tmp_path / "piece.wav", "mlx-community/whisper-large-v3-turbo")
        driver._transcribe(tmp_path / "piece.wav", "turbo")
        load_model.assert_called_once_with("turbo", device="cpu", compute_type="int8")
    finally:
        driver._load_whisper.cache_clear()
