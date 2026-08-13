"""Replayable, file-native input ledger for shadow verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Iterable, Mapping
from uuid import uuid4

from .._file_utils import _atomic_write_bytes, _atomic_write_text
from ..models import ContentItem

if TYPE_CHECKING:
    from .claims import ClaimExtractionOutcome
    from .evidence import ClaimVerificationResult


FETCHED_SCHEMA = "fetched-input/v1"
SELECTED_SCHEMA = "selected-input/v1"
MANIFEST_SCHEMA = "verification-run/v1"
DEFAULT_LEDGER_ROOT = Path("data/verification")
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9._-]+$")


class LedgerCorruptionError(RuntimeError):
    """Raised when immutable ledger content disagrees with its hash or lineage."""


def canonical_json_bytes(value: Any) -> bytes:
    """Encode JSON deterministically for IDs and content-addressed objects."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _snapshot_id(schema_version: str, payload: Mapping[str, Any]) -> str:
    return _sha256(schema_version.encode("utf-8") + b"\0" + canonical_json_bytes(payload))


def _timestamp(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("ledger timestamps must be timezone-aware")
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _stable_unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


@dataclass(frozen=True)
class FetchedInputSnapshot:
    schema_version: str
    snapshot_id: str
    captured_at: str
    item_id: str
    source_type: str
    payload: dict[str, Any]
    payload_object_hash: str
    content_present: bool
    known_content_limit: int | None = None

    def to_dict(self) -> dict[str, Any]:
        record = {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "captured_at": self.captured_at,
            "item_id": self.item_id,
            "source_type": self.source_type,
            "payload": self.payload,
            "payload_object_hash": self.payload_object_hash,
            "content_present": self.content_present,
        }
        if self.known_content_limit is not None:
            record["known_content_limit"] = self.known_content_limit
        return record


@dataclass(frozen=True)
class SelectedInputSnapshot:
    schema_version: str
    snapshot_id: str
    captured_at: str
    item_id: str
    source_type: str
    payload: dict[str, Any]
    payload_object_hash: str
    fetched_input_snapshot_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "captured_at": self.captured_at,
            "item_id": self.item_id,
            "source_type": self.source_type,
            "payload": self.payload,
            "payload_object_hash": self.payload_object_hash,
            "fetched_input_snapshot_ids": list(self.fetched_input_snapshot_ids),
        }


def build_fetched_input_snapshot(
    item: ContentItem,
    *,
    captured_at: datetime | None = None,
    known_content_limit: int | None = None,
) -> FetchedInputSnapshot:
    payload = item.model_dump(mode="json")
    payload_bytes = canonical_json_bytes(payload)
    return FetchedInputSnapshot(
        schema_version=FETCHED_SCHEMA,
        snapshot_id=_snapshot_id(FETCHED_SCHEMA, payload),
        captured_at=_timestamp(captured_at),
        item_id=item.id,
        source_type=item.source_type.value,
        payload=payload,
        payload_object_hash=_sha256(payload_bytes),
        content_present=item.content is not None,
        known_content_limit=known_content_limit,
    )


def build_selected_input_snapshot(
    item: ContentItem,
    fetched_input_snapshot_ids: Iterable[str],
    *,
    captured_at: datetime | None = None,
) -> SelectedInputSnapshot:
    payload = item.model_dump(mode="json")
    # Verify what the reader will actually see. The fetched snapshots retain the
    # original source payload and lineage; the selected snapshot is the final
    # localized artifact after enrichment. This removes the need for a second
    # model call that tried to map pre-enrichment claims back onto generated prose.
    artifacts = item.processing.artifacts if item.processing else {}
    if artifacts:
        artifact = next(iter(artifacts.values()))
        payload["title"] = artifact.title
        payload["content"] = "\n\n".join(
            f"{block.title}\n{block.content}" for block in artifact.blocks
        )
        payload["verification_language"] = artifact.language
    payload_bytes = canonical_json_bytes(payload)
    return SelectedInputSnapshot(
        schema_version=SELECTED_SCHEMA,
        snapshot_id=_snapshot_id(SELECTED_SCHEMA, payload),
        captured_at=_timestamp(captured_at),
        item_id=item.id,
        source_type=item.source_type.value,
        payload=payload,
        payload_object_hash=_sha256(payload_bytes),
        fetched_input_snapshot_ids=tuple(_stable_unique(fetched_input_snapshot_ids)),
    )


def select_shadow_items(
    items: Iterable[ContentItem], max_items: int
) -> list[ContentItem]:
    """Take reader-visible factual profiles, prioritising incident reporting."""
    priorities = {
        "censorship-watch": 0,
        "vpn-engineering": 1,
        "finance-news": 2,
        "tech-news": 3,
        "video": 4,
    }
    eligible = [
        (index, item)
        for index, item in enumerate(items)
        if item.processing
        and item.processing.classification.profile in priorities
    ]
    eligible.sort(
        key=lambda pair: (
            priorities[pair[1].processing.classification.profile],  # type: ignore[union-attr]
            pair[0],
        )
    )
    return [item for _, item in eligible[:max_items]]


@dataclass
class ShadowLedger:
    root: Path
    run_id: str
    created_at: str
    fetched_snapshots: dict[str, FetchedInputSnapshot]
    selected_snapshots: list[SelectedInputSnapshot] = field(default_factory=list)
    url_dedup_members: dict[str, list[str]] = field(default_factory=dict)
    topic_dedup_members: dict[str, list[str]] = field(default_factory=dict)
    selection_captured: bool = False
    claim_records: list[dict[str, Any]] = field(default_factory=list)
    claim_extraction: list[dict[str, Any]] = field(default_factory=list)
    claims_captured: bool = False
    claims_hash: str | None = None
    evidence_records: list[dict[str, Any]] = field(default_factory=list)
    evidence_hash: str | None = None
    report_hashes: dict[str, str] = field(default_factory=dict)
    verification_captured: bool = False

    @classmethod
    def start(
        cls,
        items: Iterable[ContentItem],
        *,
        root: Path = DEFAULT_LEDGER_ROOT,
        run_id: str | None = None,
        captured_at: datetime | None = None,
        known_content_limits: Mapping[str, int] | None = None,
    ) -> ShadowLedger:
        now = captured_at or datetime.now(timezone.utc)
        actual_run_id = run_id or f"{now:%Y%m%dT%H%M%S}-{uuid4().hex}"
        if not _SAFE_RUN_ID.fullmatch(actual_run_id):
            raise ValueError("run_id contains characters unsafe for a path")

        snapshots: dict[str, FetchedInputSnapshot] = {}
        limits = known_content_limits or {}
        for item in items:
            if item.id in snapshots:
                raise LedgerCorruptionError(f"duplicate fetched item id: {item.id}")
            snapshots[item.id] = build_fetched_input_snapshot(
                item,
                captured_at=now,
                known_content_limit=limits.get(item.id),
            )

        ledger = cls(
            root=Path(root),
            run_id=actual_run_id,
            created_at=_timestamp(now),
            fetched_snapshots=snapshots,
        )
        ledger._persist(updated_at=now)
        return ledger

    @property
    def run_dir(self) -> Path:
        return self.root / "runs" / self.run_id

    def capture_selected(
        self,
        items: Iterable[ContentItem],
        *,
        url_dedup_members: Mapping[str, Iterable[str]],
        topic_dedup_members: Mapping[str, Iterable[str]],
        captured_at: datetime | None = None,
    ) -> None:
        now = captured_at or datetime.now(timezone.utc)
        self.url_dedup_members = {
            survivor: _stable_unique(members)
            for survivor, members in url_dedup_members.items()
        }
        self.topic_dedup_members = {
            survivor: _stable_unique(members)
            for survivor, members in topic_dedup_members.items()
        }

        selected = []
        selected_ids: set[str] = set()
        for item in items:
            if item.id in selected_ids:
                raise LedgerCorruptionError(f"duplicate selected item id: {item.id}")
            selected_ids.add(item.id)
            topic_members = self.topic_dedup_members.get(item.id, [item.id])
            fetched_item_ids = _stable_unique(
                fetched_id
                for topic_member in topic_members
                for fetched_id in self.url_dedup_members.get(topic_member, [topic_member])
            )
            try:
                fetched_snapshot_ids = [
                    self.fetched_snapshots[item_id].snapshot_id
                    for item_id in fetched_item_ids
                ]
            except KeyError as exc:
                raise LedgerCorruptionError(
                    f"selected lineage references unknown fetched item: {exc.args[0]}"
                ) from exc
            selected.append(
                build_selected_input_snapshot(
                    item,
                    fetched_snapshot_ids,
                    captured_at=now,
                )
            )
        self.selected_snapshots = selected
        self.selection_captured = True
        self.claim_records = []
        self.claim_extraction = []
        self.claims_captured = False
        self.claims_hash = None
        self.evidence_records = []
        self.evidence_hash = None
        self.report_hashes = {}
        self.verification_captured = False
        self._persist(updated_at=now)

    def capture_claims(
        self,
        outcomes: Iterable[ClaimExtractionOutcome],
        *,
        captured_at: datetime | None = None,
    ) -> None:
        selected_ids = {
            snapshot.snapshot_id for snapshot in self.selected_snapshots
        }
        outcome_list = list(outcomes)
        outcome_ids = [
            outcome.selected_input_snapshot_id for outcome in outcome_list
        ]
        if len(outcome_ids) != len(set(outcome_ids)) or set(outcome_ids) != selected_ids:
            raise LedgerCorruptionError(
                "claim outcomes must cover every selected snapshot exactly once"
            )
        records = []
        extraction = []
        claim_ids: set[str] = set()
        for outcome in outcome_list:
            if outcome.selected_input_snapshot_id not in selected_ids:
                raise LedgerCorruptionError(
                    "claim outcome references an unknown selected snapshot"
                )
            if (outcome.status == "error") != (outcome.error_code is not None):
                raise LedgerCorruptionError(
                    "claim outcome status and error_code disagree"
                )
            if outcome.status == "error" and outcome.claims:
                raise LedgerCorruptionError("failed claim outcome contains claims")
            extraction.append(outcome.to_manifest())
            for claim in outcome.claims:
                if claim.selected_input_snapshot_id != outcome.selected_input_snapshot_id:
                    raise LedgerCorruptionError(
                        "claim references a different selected snapshot than its outcome"
                    )
                if claim.claim_id in claim_ids:
                    raise LedgerCorruptionError(f"duplicate claim id: {claim.claim_id}")
                claim_ids.add(claim.claim_id)
                records.append(claim.to_dict())

        claims_bytes = b"".join(
            canonical_json_bytes(record) + b"\n" for record in records
        )
        self.run_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_bytes(self.run_dir / "claims.jsonl", claims_bytes)
        self.claim_records = records
        self.claim_extraction = extraction
        self.claims_captured = True
        self.claims_hash = _sha256(claims_bytes)
        self._persist(updated_at=captured_at or datetime.now(timezone.utc))

    def capture_verification(
        self,
        claim_results: Iterable[ClaimVerificationResult],
        reports: Iterable[Mapping[str, Any]],
        *,
        captured_at: datetime | None = None,
    ) -> None:
        result_list = list(claim_results)
        expected_claim_ids = {
            record["claim_id"] for record in self.claim_records
        }
        result_claim_ids = [result.claim.claim_id for result in result_list]
        if (
            len(result_claim_ids) != len(set(result_claim_ids))
            or set(result_claim_ids) != expected_claim_ids
        ):
            raise LedgerCorruptionError(
                "claim verification results must cover every stored claim exactly once"
            )

        snapshot_records: dict[str, dict[str, Any]] = {}
        snapshots_by_id = {}
        card_records: dict[str, dict[str, Any]] = {}
        for result in result_list:
            result_snapshot_ids = {
                snapshot.snapshot_id for snapshot in result.evidence_snapshots
            }
            for snapshot in result.evidence_snapshots:
                expected_hash = _sha256(snapshot.normalized_text.encode("utf-8"))
                if expected_hash != snapshot.normalized_object_hash:
                    raise LedgerCorruptionError(
                        "evidence normalized text does not match its object hash"
                    )
                existing = snapshot_records.get(snapshot.snapshot_id)
                record = snapshot.to_dict()
                identity_fields = (
                    "schema_version",
                    "normalized_object_hash",
                    "final_url",
                    "access_status",
                    "normalizer",
                    "normalized_text",
                )
                if existing is not None and any(
                    existing[field] != record[field] for field in identity_fields
                ):
                    raise LedgerCorruptionError(
                        f"conflicting evidence snapshot id: {snapshot.snapshot_id}"
                    )
                snapshot_records.setdefault(snapshot.snapshot_id, record)
                snapshots_by_id.setdefault(snapshot.snapshot_id, snapshot)
            for card in result.evidence_cards:
                if card.claim_id != result.claim.claim_id:
                    raise LedgerCorruptionError(
                        "evidence card references a different claim than its result"
                    )
                if card.evidence_snapshot_id not in result_snapshot_ids:
                    raise LedgerCorruptionError(
                        "evidence card snapshot is absent from its claim result"
                    )
                snapshot = snapshots_by_id.get(card.evidence_snapshot_id)
                if snapshot is None:
                    raise LedgerCorruptionError(
                        "evidence card references an unknown evidence snapshot"
                    )
                if (
                    snapshot.normalized_text[card.excerpt_start : card.excerpt_end]
                    != card.excerpt
                ):
                    raise LedgerCorruptionError(
                        "evidence card excerpt does not round-trip to its snapshot"
                    )
                record = card.to_dict()
                existing = card_records.get(card.evidence_id)
                if existing is not None and existing != record:
                    raise LedgerCorruptionError(
                        f"conflicting evidence card id: {card.evidence_id}"
                    )
                card_records[card.evidence_id] = record

        records = [
            {"record_type": "snapshot", **record}
            for record in snapshot_records.values()
        ] + [
            {"record_type": "card", **record}
            for record in card_records.values()
        ]
        evidence_bytes = b"".join(
            canonical_json_bytes(record) + b"\n" for record in records
        )
        self.run_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_bytes(self.run_dir / "evidence.jsonl", evidence_bytes)
        for snapshot in snapshots_by_id.values():
            object_path = (
                self.root
                / "objects"
                / "sha256"
                / snapshot.normalized_object_hash[:2]
                / snapshot.normalized_object_hash
            )
            _write_immutable_bytes(
                object_path,
                snapshot.normalized_text.encode("utf-8"),
            )

        report_hashes = {}
        (self.run_dir / "reports").mkdir(parents=True, exist_ok=True)
        known_selected_ids = {
            snapshot.snapshot_id for snapshot in self.selected_snapshots
        }
        report_list = list(reports)
        report_selected_ids = [
            report.get("selected_input_snapshot_id") for report in report_list
        ]
        if (
            len(report_selected_ids) != len(set(report_selected_ids))
            or set(report_selected_ids) != known_selected_ids
        ):
            raise LedgerCorruptionError(
                "verification reports must cover every selected snapshot exactly once"
            )
        for report in report_list:
            report_id = report.get("report_id")
            selected_id = report.get("selected_input_snapshot_id")
            if (
                not isinstance(report_id, str)
                or not re.fullmatch(r"[0-9a-f]{64}", report_id)
            ):
                raise LedgerCorruptionError("report_id is not a safe SHA-256 id")
            if selected_id not in known_selected_ids:
                raise LedgerCorruptionError(
                    "verification report references an unknown selected snapshot"
                )
            report_bytes = canonical_json_bytes(dict(report)) + b"\n"
            _atomic_write_bytes(
                self.run_dir / "reports" / f"{report_id}.json",
                report_bytes,
            )
            report_hashes[report_id] = _sha256(report_bytes)

        self.evidence_records = records
        self.evidence_hash = _sha256(evidence_bytes)
        self.report_hashes = report_hashes
        self.verification_captured = True
        self._persist(updated_at=captured_at or datetime.now(timezone.utc))

    def _persist(self, *, updated_at: datetime) -> None:
        records = [
            {"snapshot_type": "fetched", **snapshot.to_dict()}
            for snapshot in self.fetched_snapshots.values()
        ] + [
            {"snapshot_type": "selected", **snapshot.to_dict()}
            for snapshot in self.selected_snapshots
        ]

        for snapshot in (*self.fetched_snapshots.values(), *self.selected_snapshots):
            object_path = (
                self.root
                / "objects"
                / "sha256"
                / snapshot.payload_object_hash[:2]
                / snapshot.payload_object_hash
            )
            _write_immutable_bytes(
                object_path,
                canonical_json_bytes(snapshot.payload),
            )

        input_bytes = b"".join(canonical_json_bytes(record) + b"\n" for record in records)
        input_hash = _sha256(input_bytes)
        input_relative = Path("inputs") / f"{input_hash}.jsonl"
        _write_immutable_bytes(
            self.run_dir / input_relative,
            input_bytes,
        )

        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "updated_at": _timestamp(updated_at),
            "stage": (
                "evidence"
                if self.verification_captured
                else "claims"
                if self.claims_captured
                else "selected"
                if self.selection_captured
                else "fetched"
            ),
            "input_ledger": input_relative.as_posix(),
            "input_ledger_hash": input_hash,
            "fetched_snapshot_count": len(self.fetched_snapshots),
            "selected_snapshot_count": len(self.selected_snapshots),
            "url_dedup_members": self.url_dedup_members,
            "topic_dedup_members": self.topic_dedup_members,
        }
        if self.claims_captured:
            manifest.update(
                {
                    "claims_file": "claims.jsonl",
                    "claims_hash": self.claims_hash,
                    "claim_count": len(self.claim_records),
                    "claim_extraction": self.claim_extraction,
                }
            )
        if self.verification_captured:
            manifest.update(
                {
                    "evidence_file": "evidence.jsonl",
                    "evidence_hash": self.evidence_hash,
                    "evidence_record_count": len(self.evidence_records),
                    "reports": self.report_hashes,
                }
            )
        self.run_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(
            self.run_dir / "manifest.json",
            canonical_json_bytes(manifest).decode("utf-8") + "\n",
        )


def _write_immutable_bytes(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise LedgerCorruptionError(f"immutable ledger object is corrupt: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_bytes(path, content)
