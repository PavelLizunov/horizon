"""Regression checks for the deployment order that Telegram links depend on."""

from pathlib import Path


def test_readable_site_is_shipped_before_narration():
    script = (
        Path(__file__).resolve().parents[1] / "deploy" / "run-daily.sh"
    ).read_text(encoding="utf-8")
    daily_job = script[script.index('log "pipeline: start"') :]

    first_ship = daily_job.index("ship_site || exit 1")
    narration = daily_job.index("# Narration.")
    second_ship = daily_job.rindex("ship_site || exit 1")

    assert first_ship < narration < second_ship


def test_ship_only_mode_exits_before_paid_pipeline():
    script = (
        Path(__file__).resolve().parents[1] / "deploy" / "run-daily.sh"
    ).read_text(encoding="utf-8")

    ship_only = script.index('if [[ "${HORIZON_SHIP_ONLY:-0}" == "1" ]]')
    paid_pipeline = script.index('.venv/bin/horizon --hours')

    assert ship_only < paid_pipeline
    assert "ship_site\n  exit $?" in script[ship_only:paid_pipeline]


def test_narration_ships_each_attachment_without_recursion_or_pull():
    script = (
        Path(__file__).resolve().parents[1] / "deploy" / "run-daily.sh"
    ).read_text(encoding="utf-8")
    narration = script[script.index("# Narration.") :]
    assert "--after-attach env HORIZON_SHIP_ONLY=1 HORIZON_NO_PULL=1" in narration
    assert 'zsh "$PWD/deploy/run-daily.sh"' in narration
    assert narration.index("--after-attach") < narration.rindex("ship_site || exit 1")


def test_daily_runner_executes_per_article_hook_offline(tmp_path):
    """Exercise actual shell wiring; all production commands are local stubs."""
    import os
    import shutil
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    (tmp_path / "deploy").mkdir()
    script = tmp_path / "deploy" / "run-daily.sh"
    shutil.copyfile(root / "deploy" / "run-daily.sh", script)
    (tmp_path / "docs" / "digest" / "2026-01-01-ru").mkdir(parents=True)
    (tmp_path / "site").mkdir()
    (tmp_path / "data").mkdir()
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    journal = tmp_path / "events"
    interpreter = sys.executable

    def executable(path, body):
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)

    executable(venv / "horizon", '#!/bin/bash\necho pipeline >> "$TEST_EVENTS"\n')
    executable(binaries / "mkdocs", '#!/bin/bash\necho ship >> "$TEST_EVENTS"\n')
    executable(venv / "python", f'#!{interpreter}\n' + '''
import pathlib, sys
if "--write-all" in sys.argv:
    out = pathlib.Path(sys.argv[sys.argv.index("--write-all") + 1])
    out.mkdir(parents=True, exist_ok=True)
    (out / "issue__article.txt").write_text("text")
''')
    narrator = binaries / "narrator"
    executable(narrator, f'#!{interpreter}\n' + '''
import os, subprocess, sys
with open(os.environ["TEST_EVENTS"], "a") as log:
    log.write("narration\\n")
hook = sys.argv[sys.argv.index("--after-attach") + 1:]
for article in ("first", "second"):
    with open(os.environ["TEST_EVENTS"], "a") as log:
        log.write(f"attach-{article}\\n")
    subprocess.run(hook, check=True)
''')
    # The runner's current shell syntax is bash-compatible. Use zsh if present,
    # otherwise a bash shim tests the control flow without installing anything.
    shell = shutil.which("zsh") or shutil.which("bash")
    executable(binaries / "zsh", f'#!/bin/bash\nexec "{shell}" "$@"\n')
    executable(binaries / "ssh", '#!/bin/bash\ncat > /dev/null\n')
    env = {
        **os.environ, "HOME": str(tmp_path),
        "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
        "TEST_EVENTS": str(journal), "HORIZON_NO_PULL": "1",
        "HORIZON_SHIP_ONLY": "0", "HORIZON_TTS_PYTHON": str(narrator),
        "HORIZON_DIR": str(tmp_path),
        "TMPDIR": str(tmp_path), "HORIZON_SITE_HOST": "unused.invalid",
        "HORIZON_SITE_PATH": "/unused",
    }
    result = subprocess.run([shell, str(script)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert journal.read_text().splitlines() == [
        "pipeline", "ship", "narration", "attach-first", "ship",
        "attach-second", "ship", "ship",
    ], result.stdout + result.stderr
