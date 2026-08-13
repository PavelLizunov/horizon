"""Small persistent state machine for censorship and VPN incidents."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable
import unicodedata

from .._file_utils import _atomic_write_text
from ..models import ContentItem


SCHEMA_VERSION = "incident-ledger/v1"
INCIDENT_PROFILES = {"censorship-watch", "vpn-engineering"}
_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)


def update_incident_ledger(
    path: Path,
    records: Iterable[tuple[ContentItem, dict[str, Any]]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Merge reader-visible event checks into a durable, local JSON ledger."""
    checked = now or datetime.now(timezone.utc)
    if checked.tzinfo is None:
        raise ValueError("incident timestamps must be timezone-aware")
    checked_at = _timestamp(checked)
    ledger = _load(path)
    incidents = ledger["incidents"]

    for item, public in records:
        profile = (
            item.processing.classification.profile if item.processing else None
        )
        if profile not in INCIDENT_PROFILES:
            continue
        claims = public.get("claims")
        if not isinstance(claims, list):
            continue
        for claim in claims:
            if not isinstance(claim, dict) or claim.get("kind") != "event":
                continue
            text = str(claim.get("text") or "").strip()
            if not text:
                continue
            incident_id = _incident_id(profile, text)
            new_state = _state(item, str(claim.get("public_status") or ""))
            entry = incidents.get(incident_id)
            if not isinstance(entry, dict):
                entry = {
                    "incident_id": incident_id,
                    "profile": profile,
                    "claim": text,
                    "first_seen_at": checked_at,
                    "state": new_state,
                    "state_history": [],
                    "source_item_ids": [],
                    "source_urls": [],
                }
                incidents[incident_id] = entry
            history = entry.setdefault("state_history", [])
            if entry.get("state") != new_state or not history:
                history.append(
                    {"state": new_state, "changed_at": checked_at}
                )
            entry["state"] = new_state
            entry["last_seen_at"] = checked_at
            entry["last_checked_at"] = str(public.get("checked_at") or checked_at)
            next_check = public.get("next_check_at")
            if isinstance(next_check, str) and next_check:
                entry["next_check_at"] = next_check
            else:
                entry.pop("next_check_at", None)
            item_ids = entry.setdefault("source_item_ids", [])
            if item.id not in item_ids:
                item_ids.append(item.id)
            urls = entry.setdefault("source_urls", [])
            url = str(item.url)
            if url not in urls:
                urls.append(url)

    ledger["updated_at"] = checked_at
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(
        path,
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return ledger


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "incidents": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported incident ledger schema")
    if not isinstance(value.get("incidents"), dict):
        raise ValueError("invalid incident ledger")
    return value


def _incident_id(profile: str, claim: str) -> str:
    normalized = unicodedata.normalize("NFKC", claim).casefold()
    normalized = " ".join(part for part in _TOKEN_RE.split(normalized) if part)
    digest = hashlib.sha256(f"{profile}\0{normalized}".encode("utf-8")).hexdigest()
    return f"incident-{digest[:20]}"


def _state(item: ContentItem, public_status: str) -> str:
    if item.metadata.get("incident_resolution") is True:
        return "RESOLVED"
    if public_status == "disputed":
        return "DISPUTED"
    if public_status == "corroborated_event":
        return "CORROBORATED"
    return "PROVISIONAL"


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
