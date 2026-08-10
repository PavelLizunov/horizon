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
