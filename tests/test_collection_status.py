from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.dev_collection_status import build_page


NOW = datetime(2026, 8, 15, 12, tzinfo=timezone.utc)


def test_collection_page_uses_active_config_without_secret_fields(tmp_path) -> None:
    config = json.loads(Path("data/config.example.json").read_text(encoding="utf-8"))
    config["ai"]["api_key_env"] = "DO_NOT_PUBLISH_THIS"
    config["sources"]["rss"].append(
        {
            "name": "Private query feed",
            "url": "https://feeds.example/items?api_key=DO_NOT_PUBLISH_THIS",
            "enabled": True,
            "profile": "vpn-engineering",
        }
    )
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    page = build_page(config_path, tmp_path / "runs", now=NOW)

    assert "# Что мы собираем" in page
    assert "VPN: технологии и протоколы" in page
    assert "Блокировки и доступность сети" in page
    assert "SagerNet/sing-box" in page
    assert "@zatelecom" in page
    assert "OONI Blog" in page
    assert "Private query feed" in page
    assert "https://feeds.example/items" in page
    assert "api_key" not in page
    assert "DO_NOT_PUBLISH_THIS" not in page


def test_collection_page_shows_last_run_counts_and_staleness(tmp_path) -> None:
    config = json.loads(Path("data/config.example.json").read_text(encoding="utf-8"))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    run = tmp_path / "runs" / "20260813T090000-run"
    run.joinpath("inputs").mkdir(parents=True)
    records = [
        {"snapshot_type": "fetched", "source_type": "github"},
        {"snapshot_type": "fetched", "source_type": "telegram"},
        {
            "snapshot_type": "selected",
            "source_type": "telegram",
            "payload": {
                "processing": {"classification": {"profile": "censorship-watch"}}
            },
        },
    ]
    run.joinpath("inputs", "items.jsonl").write_text(
        "\n".join(json.dumps(row) for row in records), encoding="utf-8"
    )
    run.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-08-13T09:00:00Z",
                "input_ledger": "inputs/items.jsonl",
            }
        ),
        encoding="utf-8",
    )

    page = build_page(config_path, tmp_path / "runs", now=NOW)

    assert "Собрано материалов: **2**" in page
    assert "в проверочной выборке: **1**" in page
    assert "GitHub: 1" in page
    assert "Telegram: 1" in page
    assert "Блокировки и доступность сети: 1" in page
    assert "Сбор давно не обновлялся" in page
