from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.models import (
    AIConfig,
    ClassificationResult,
    Config,
    ContentAnalysis,
    ContentItem,
    ProcessingConfig,
    ProcessingResult,
    ProfileSettingsConfig,
    SourceType,
    SourcesConfig,
    VerificationConfig,
)
from src.orchestrator import HorizonOrchestrator
from src.verification import ledger as ledger_module
from src.verification.ledger import (
    LedgerCorruptionError,
    ShadowLedger,
    build_fetched_input_snapshot,
    canonical_json_bytes,
)


NOW = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)


def _item(
    item_id: str,
    url: str | None = None,
    *,
    source_type: SourceType = SourceType.RSS,
    content: str | None = None,
) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=source_type,
        title=f"Title {item_id}",
        url=url or f"https://example.com/{item_id}",
        content=content,
        published_at=NOW,
        fetched_at=NOW,
        profile="tech-news",
    )


def _analyzed(item: ContentItem, score: float) -> ContentItem:
    item.processing = ProcessingResult(
        classification=ClassificationResult(
            profile="tech-news", method="source_override"
        ),
        analysis=ContentAnalysis(
            score=score,
            reason="test",
            summary=item.title,
        ),
    )
    return item


def test_canonical_json_and_snapshot_ids_are_deterministic() -> None:
    assert canonical_json_bytes({"b": 2, "a": "ёж"}) == '{"a":"ёж","b":2}'.encode()
    item = _item("one", content="evidence")

    first = build_fetched_input_snapshot(item, captured_at=NOW)
    second = build_fetched_input_snapshot(
        item,
        captured_at=NOW + timedelta(hours=1),
    )

    assert first.snapshot_id == second.snapshot_id
    assert first.payload_object_hash == hashlib.sha256(
        canonical_json_bytes(first.payload)
    ).hexdigest()
    assert first.content_present is True


def test_shadow_ledger_uses_immutable_objects_and_atomic_manifest(tmp_path, monkeypatch) -> None:
    item = _item("one", content="body")
    ledger = ShadowLedger.start(
        [item],
        root=tmp_path,
        run_id="run-atomic",
        captured_at=NOW,
    )
    manifest_path = ledger.run_dir / "manifest.json"
    original_manifest = manifest_path.read_bytes()
    manifest = json.loads(original_manifest)
    original_input = ledger.run_dir / manifest["input_ledger"]
    assert hashlib.sha256(original_input.read_bytes()).hexdigest() == manifest[
        "input_ledger_hash"
    ]

    real_atomic_write = ledger_module._atomic_write_text

    def fail_manifest(path: Path, content: str) -> None:
        if path.name == "manifest.json":
            raise OSError("replace failed")
        real_atomic_write(path, content)

    monkeypatch.setattr(ledger_module, "_atomic_write_text", fail_manifest)
    with pytest.raises(OSError, match="replace failed"):
        ledger.capture_selected(
            [item],
            url_dedup_members={"one": ["one"]},
            topic_dedup_members={"one": ["one"]},
            captured_at=NOW + timedelta(minutes=1),
        )

    assert manifest_path.read_bytes() == original_manifest
    assert original_input.exists()


def test_shadow_ledger_rejects_corrupt_content_addressed_object(tmp_path) -> None:
    item = _item("one", content="body")
    ledger = ShadowLedger.start(
        [item], root=tmp_path, run_id="run-corrupt", captured_at=NOW
    )
    snapshot = ledger.fetched_snapshots["one"]
    object_path = (
        tmp_path
        / "objects"
        / "sha256"
        / snapshot.payload_object_hash[:2]
        / snapshot.payload_object_hash
    )
    object_path.write_text("tampered", encoding="utf-8")

    with pytest.raises(LedgerCorruptionError, match="corrupt"):
        ledger.capture_selected(
            [item],
            url_dedup_members={"one": ["one"]},
            topic_dedup_members={"one": ["one"]},
            captured_at=NOW,
        )


def test_both_dedup_passes_return_complete_member_maps(monkeypatch) -> None:
    orchestrator = object.__new__(HorizonOrchestrator)
    url_members: dict[str, list[str]] = {}
    url_items = [
        _item("short", "https://example.com/story", content="short"),
        _item(
            "rich",
            "https://example.com/story/",
            source_type=SourceType.REDDIT,
            content="much richer content",
        ),
        _item("other", content="other topic"),
    ]
    merged = orchestrator.merge_cross_source_duplicates(
        url_items, member_map=url_members
    )

    class FakeAI:
        async def complete(self, **kwargs):  # type: ignore[no-untyped-def]
            return '{"duplicates":[[0,1]]}'

    orchestrator.config = SimpleNamespace(ai=SimpleNamespace())
    monkeypatch.setattr("src.orchestrator.create_ai_client", lambda config: FakeAI())
    topic_members: dict[str, list[str]] = {}
    topic_result = asyncio.run(
        orchestrator.merge_topic_duplicates(
            merged,
            log=False,
            member_map=topic_members,
        )
    )

    assert [item.id for item in merged] == ["rich", "other"]
    assert url_members == {"rich": ["short", "rich"], "other": ["other"]}
    assert [item.id for item in topic_result] == ["rich"]
    assert topic_members == {"rich": ["rich", "other"]}


def test_enabled_shadow_run_captures_exact_pre_enrichment_input_and_lineage(
    tmp_path, monkeypatch
) -> None:
    config = Config(
        ai=AIConfig(
            provider="openai",
            model="test",
            api_key_env="TEST_API_KEY",
            languages=[],
        ),
        sources=SourcesConfig(),
        processing=ProcessingConfig(
            profile_settings={
                "tech-news": ProfileSettingsConfig(threshold=1.0)
            }
        ),
        verification=VerificationConfig(enabled=True),
    )
    orchestrator = HorizonOrchestrator(config, SimpleNamespace())
    raw_items = [
        _item("short", "https://example.com/story", content="short"),
        _item(
            "rich",
            "https://example.com/story/",
            source_type=SourceType.REDDIT,
            content="much richer content",
        ),
        _item("other", content="other topic"),
    ]
    enriched_content = []

    async def fetch_all_sources(since):  # type: ignore[no-untyped-def]
        return raw_items

    async def analyze_items(items):  # type: ignore[no-untyped-def]
        return [_analyzed(item, 9 - index) for index, item in enumerate(items)]

    class FakeAI:
        async def complete(self, **kwargs):  # type: ignore[no-untyped-def]
            if "core factual claims" in kwargs["system"]:
                return json.dumps(
                    {
                        "claims": [
                            {
                                "source_field": "title",
                                "source_text": "Title rich",
                                "normalized_claim": "The rich item was announced",
                                "kind": "announcement",
                                "importance": "headline",
                                "checkability": "not_checkable",
                            }
                        ]
                    }
                )
            return '{"duplicates":[[0,1]]}'

    async def expand_twitter(items):  # type: ignore[no-untyped-def]
        items[0].content = f"{items[0].content}\nTWITTER DISCUSSION"

    async def enrich_items(items):  # type: ignore[no-untyped-def]
        enriched_content.append(items[0].content)
        items[0].content = f"{items[0].content}\nENRICHED"

    monkeypatch.setattr(orchestrator, "fetch_all_sources", fetch_all_sources)
    monkeypatch.setattr(orchestrator, "analyze_items", analyze_items)
    monkeypatch.setattr(orchestrator, "_expand_twitter_discussion", expand_twitter)
    monkeypatch.setattr(orchestrator, "enrich_items", enrich_items)
    monkeypatch.setattr("src.orchestrator.create_ai_client", lambda config: FakeAI())
    monkeypatch.chdir(tmp_path)

    asyncio.run(orchestrator.run())

    run_dirs = list((tmp_path / "data" / "verification" / "runs").iterdir())
    assert len(run_dirs) == 1
    manifest = json.loads((run_dirs[0] / "manifest.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (run_dirs[0] / manifest["input_ledger"])
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    selected = next(record for record in records if record["snapshot_type"] == "selected")
    fetched = {
        record["item_id"]: record
        for record in records
        if record["snapshot_type"] == "fetched"
    }

    assert manifest["stage"] == "evidence"
    assert manifest["url_dedup_members"] == {
        "other": ["other"],
        "rich": ["short", "rich"],
    }
    assert manifest["topic_dedup_members"] == {"rich": ["rich", "other"]}
    assert selected["item_id"] == "rich"
    assert selected["fetched_input_snapshot_ids"] == [
        fetched["short"]["snapshot_id"],
        fetched["rich"]["snapshot_id"],
        fetched["other"]["snapshot_id"],
    ]
    assert "TWITTER DISCUSSION" in selected["payload"]["content"]
    assert "ENRICHED" not in selected["payload"]["content"]
    assert "TWITTER DISCUSSION" in enriched_content[0]
    claims = [
        json.loads(line)
        for line in (run_dirs[0] / "claims.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(claims) == 1
    assert selected["payload"][claims[0]["source_field"]][
        claims[0]["source_start"] : claims[0]["source_end"]
    ] == claims[0]["source_text"]
    assert manifest["claim_extraction"][0]["duration_seconds"] >= 0
    report_id = next(iter(manifest["reports"]))
    report = json.loads(
        (run_dirs[0] / "reports" / f"{report_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["duration_seconds"] >= 0
    assert report["artifact_audit"]["status"] == "ok"


def test_verification_is_disabled_by_default_and_writes_nothing(
    tmp_path, monkeypatch
) -> None:
    config = Config(
        ai=AIConfig(
            provider="openai",
            model="test",
            api_key_env="TEST_API_KEY",
            languages=[],
        ),
        sources=SourcesConfig(),
        processing=ProcessingConfig(
            profile_settings={
                "tech-news": ProfileSettingsConfig(threshold=1.0)
            }
        ),
    )
    assert config.verification.enabled is False
    assert config.verification.publish_to_site is False
    orchestrator = HorizonOrchestrator(config, SimpleNamespace())
    item = _analyzed(_item("one", content="body"), 9.0)
    enriched_ids = []

    async def fetch_all_sources(since):  # type: ignore[no-untyped-def]
        return [item]

    async def analyze_items(items):  # type: ignore[no-untyped-def]
        return items

    async def expand_twitter(items):  # type: ignore[no-untyped-def]
        return None

    async def enrich_items(items):  # type: ignore[no-untyped-def]
        enriched_ids.extend(value.id for value in items)

    monkeypatch.setattr(orchestrator, "fetch_all_sources", fetch_all_sources)
    monkeypatch.setattr(orchestrator, "analyze_items", analyze_items)
    monkeypatch.setattr(orchestrator, "_expand_twitter_discussion", expand_twitter)
    monkeypatch.setattr(orchestrator, "enrich_items", enrich_items)
    monkeypatch.chdir(tmp_path)

    asyncio.run(orchestrator.run())

    assert enriched_ids == ["one"]
    assert not (tmp_path / "data" / "verification").exists()


def test_verification_limits_are_validated() -> None:

    with pytest.raises(ValidationError):
        VerificationConfig(max_core_claims_per_item=4)

    with pytest.raises(ValidationError):
        VerificationConfig(input_price_per_million_usd=0.2)

    with pytest.raises(ValidationError):
        VerificationConfig(cached_input_price_per_million_usd=0.0028)
