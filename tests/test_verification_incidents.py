from datetime import datetime, timedelta, timezone

from src.models import (
    ClassificationResult,
    ContentItem,
    ProcessingResult,
    SourceType,
)
from src.verification.incidents import update_incident_ledger


NOW = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)


def _item(item_id: str, *, resolved: bool = False) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=SourceType.TELEGRAM,
        title="Access incident",
        url=f"https://example.com/{item_id}",
        content="Observed on one network.",
        published_at=NOW,
        metadata={"incident_resolution": resolved},
        processing=ProcessingResult(
            classification=ClassificationResult(
                profile="censorship-watch", method="source_override"
            )
        ),
    )


def _public(status: str) -> dict:
    return {
        "checked_at": "2026-08-14T08:00:00Z",
        "next_check_at": "2026-08-15T08:00:00Z",
        "claims": [
            {
                "kind": "event",
                "text": "Protocol X failed on network Y",
                "public_status": status,
            }
        ],
    }


def test_incident_ledger_persists_state_transitions(tmp_path) -> None:
    path = tmp_path / "incidents.json"

    first = update_incident_ledger(
        path, [(_item("one"), _public("provisional"))], now=NOW
    )
    incident_id = next(iter(first["incidents"]))
    assert first["incidents"][incident_id]["state"] == "PROVISIONAL"

    second = update_incident_ledger(
        path,
        [(_item("two"), _public("corroborated_event"))],
        now=NOW + timedelta(hours=4),
    )
    incident = second["incidents"][incident_id]
    assert incident["state"] == "CORROBORATED"
    assert [row["state"] for row in incident["state_history"]] == [
        "PROVISIONAL",
        "CORROBORATED",
    ]
    assert incident["source_item_ids"] == ["one", "two"]


def test_incident_resolution_is_explicit_and_non_event_claims_are_ignored(
    tmp_path,
) -> None:
    path = tmp_path / "incidents.json"
    public = _public("corroborated_event")
    public["claims"].append(
        {"kind": "release", "text": "Version 2 shipped", "public_status": "official_release"}
    )

    ledger = update_incident_ledger(
        path, [(_item("one", resolved=True), public)], now=NOW
    )

    assert len(ledger["incidents"]) == 1
    assert next(iter(ledger["incidents"].values()))["state"] == "RESOLVED"
