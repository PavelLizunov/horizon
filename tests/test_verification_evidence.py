from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from src.models import ContentItem, SourceType
from src.processing.tools import SearchHit, SearchOutcome
from src.verification.claims import ClaimCard, ClaimExtractionOutcome
from src.verification.evidence import (
    ASSESSMENT_PROMPT_VERSION,
    AdjudicationResult,
    ClaimVerificationResult,
    EvidenceAssessmentProposal,
    EvidenceCard,
    EvidenceVerifier,
    ItemVerificationBudget,
    adjudicate_claim,
    anchor_evidence_assessments,
    build_evidence_snapshot,
    build_public_verification,
    build_query_templates,
    build_token_usage_report,
    build_verification_report,
)
from src.verification.fetch import DocumentFetchOutcome
from src.verification.ledger import ShadowLedger, build_selected_input_snapshot


NOW = datetime(2026, 8, 11, tzinfo=timezone.utc)


def _claim(
    *,
    kind: str = "release",
    checkability: str = "checkable",
    claim_id: str = "claim-1",
) -> ClaimCard:
    return ClaimCard(
        claim_id=claim_id,
        selected_input_snapshot_id="selected-1",
        source_field="title",
        source_start=0,
        source_end=18,
        source_text="Product X released",
        normalized_claim="Product X version 2 was released on August 11",
        kind=kind,  # type: ignore[arg-type]
        importance="headline",
        checkability=checkability,  # type: ignore[arg-type]
    )


def _selected(url: str = "https://vendor.example/release"):
    item = ContentItem(
        id="rss:item-1",
        source_type=SourceType.RSS,
        title="Product X released",
        url=url,
        content="Product X version 2 was released on August 11.",
        published_at=NOW,
        fetched_at=NOW,
    )
    return build_selected_input_snapshot(item, ["fetched-1"], captured_at=NOW)


def _fetch_outcome(
    url: str,
    content: bytes,
    mime_type: str = "text/plain",
) -> DocumentFetchOutcome:
    return DocumentFetchOutcome(
        status="ok",
        requested_url=url,
        final_url=url,
        http_status=200,
        mime_type=mime_type,
        content=content,
    )


def _card(
    *,
    stance: str,
    source_class: str = "original",
    interested_party: bool = False,
    quantity_match: str = "match",
    origin_key: str | None = "url:https://source.example/",
    evidence_id: str = "evidence-1",
) -> EvidenceCard:
    return EvidenceCard(
        evidence_id=evidence_id,
        claim_id="claim-1",
        evidence_snapshot_id="snapshot-1",
        excerpt_start=0,
        excerpt_end=8,
        excerpt="evidence",
        source_class=source_class,  # type: ignore[arg-type]
        interested_party=interested_party,
        stance=stance,  # type: ignore[arg-type]
        entity_match="match",
        temporal_match="match",
        quantity_match=quantity_match,  # type: ignore[arg-type]
        origin_key=origin_key,
        assessment_model="test",
    )


def test_evidence_snapshot_normalizes_html_and_hashes_exact_text() -> None:
    outcome = _fetch_outcome(
        "https://example.com/article#fragment",
        b"<html><script>secret()</script><body><h1>Release</h1><p>Version 2 shipped.</p></body></html>",
        "text/html",
    )

    snapshot = build_evidence_snapshot(outcome, retrieved_at=NOW)

    assert snapshot is not None
    assert "secret" not in snapshot.normalized_text
    assert "Version 2 shipped" in snapshot.normalized_text
    assert snapshot.normalized_object_hash == hashlib.sha256(
        snapshot.normalized_text.encode()
    ).hexdigest()
    assert snapshot.snapshot_id == build_evidence_snapshot(
        outcome, retrieved_at=NOW
    ).snapshot_id


def test_query_templates_are_deterministic_and_include_counterquery() -> None:
    queries = build_query_templates(_claim())

    assert queries == build_query_templates(_claim())
    assert len(queries) == 3
    assert "official release changelog" in queries[0]
    assert "Product X" in queries[1]
    assert "correction denied false" in queries[2]


def test_public_verification_contains_claim_status_and_links_only() -> None:
    snapshot = build_evidence_snapshot(
        _fetch_outcome(
            "https://vendor.example/release",
            b"Product X version 2 was officially released on August 11.",
        ),
        retrieved_at=NOW,
    )
    assert snapshot is not None
    card = replace(
        _card(stance="supports"),
        evidence_snapshot_id=snapshot.snapshot_id,
    )
    result = ClaimVerificationResult(
        claim=_claim(),
        adjudication=AdjudicationResult(status="supported_by_evidence"),
        evidence_snapshots=(snapshot,),
        evidence_cards=(card, replace(card, evidence_id="duplicate")),
        stop_reason="sufficient",
        search_calls=1,
        documents_attempted=1,
        documents_fetched=1,
        cache_reuse=0,
    )

    public = build_public_verification([result])

    assert public == {
        "schema_version": "public-verification/v1",
        "state": "checked",
        "claims": [
            {
                "text": "Product X version 2 was released on August 11",
                "status": "supported_by_evidence",
                "sources": [
                    {
                        "url": "https://vendor.example/release",
                        "stance": "supports",
                    }
                ],
            }
        ],
    }
    assert "normalized_text" not in str(public)
    assert "excerpt" not in str(public)


def test_token_usage_report_prices_cached_input_separately() -> None:
    usage = build_token_usage_report(
        100_000,
        10_000,
        model="deepseek-v4-flash",
        cached_input_tokens=80_000,
        input_price_per_million_usd=0.14,
        cached_input_price_per_million_usd=0.0028,
        output_price_per_million_usd=0.28,
        quota_name="OpenCode Go",
    )

    assert usage == {
        "model": "deepseek-v4-flash",
        "input_tokens": 100_000,
        "cached_input_tokens": 80_000,
        "uncached_input_tokens": 20_000,
        "output_tokens": 10_000,
        "total_tokens": 110_000,
        "quota_name": "OpenCode Go",
        "estimated_cost_usd": 0.005824,
        "pricing": {
            "input_per_million_usd": 0.14,
            "cached_input_per_million_usd": 0.0028,
            "output_per_million_usd": 0.28,
        },
    }


def test_public_verification_preserves_opposing_stances_from_same_url() -> None:
    snapshot = build_evidence_snapshot(
        _fetch_outcome("https://source.example/story", b"Evidence text"),
        retrieved_at=NOW,
    )
    assert snapshot is not None
    support = replace(
        _card(stance="supports"),
        evidence_snapshot_id=snapshot.snapshot_id,
    )
    contradiction = replace(
        support,
        evidence_id="evidence-2",
        stance="contradicts",
    )
    result = ClaimVerificationResult(
        claim=_claim(),
        adjudication=AdjudicationResult(status="mixed_evidence"),
        evidence_snapshots=(snapshot,),
        evidence_cards=(support, contradiction),
        stop_reason="sufficient",
        search_calls=1,
        documents_attempted=1,
        documents_fetched=1,
        cache_reuse=0,
    )

    sources = build_public_verification([result])["claims"][0]["sources"]

    assert [source["stance"] for source in sources] == ["supports", "contradicts"]


def test_assessment_excerpt_round_trips_and_exact_copies_share_origin() -> None:
    text = b"Product X version 2 was officially released on August 11."
    first = build_evidence_snapshot(
        _fetch_outcome("https://vendor.example/release", text), retrieved_at=NOW
    )
    second = build_evidence_snapshot(
        _fetch_outcome("https://mirror.example/release", text), retrieved_at=NOW
    )
    assert first is not None and second is not None
    proposals = [
        EvidenceAssessmentProposal(
            candidate_id=snapshot.snapshot_id,
            excerpt="Product X version 2 was officially released on August 11.",
            source_class="original" if index == 0 else "independent_reporting",
            interested_party=index == 0,
            stance="supports",
            entity_match="match",
            temporal_match="match",
            quantity_match="unknown",
        )
        for index, snapshot in enumerate((first, second))
    ]

    cards = anchor_evidence_assessments(
        _claim(), (first, second), proposals, model="test-model"
    )

    assert len(cards) == 2
    assert cards[0].origin_key == cards[1].origin_key
    assert cards[0].origin_key == f"copy:{first.normalized_object_hash}"
    for card, snapshot in zip(cards, (first, second)):
        assert snapshot.normalized_text[card.excerpt_start : card.excerpt_end] == card.excerpt
        assert card.assessment_prompt_version == ASSESSMENT_PROMPT_VERSION


def test_assessment_rejects_ambiguous_or_missing_exact_excerpt() -> None:
    snapshot = build_evidence_snapshot(
        _fetch_outcome("https://example.com", b"same text and same text"),
        retrieved_at=NOW,
    )
    assert snapshot is not None
    proposal = EvidenceAssessmentProposal(
        candidate_id=snapshot.snapshot_id,
        excerpt="same text",
        source_class="unknown",
        interested_party=False,
        stance="context",
        entity_match="match",
        temporal_match="match",
        quantity_match="unknown",
    )

    with pytest.raises(ValueError, match="ambiguous"):
        anchor_evidence_assessments(_claim(), [snapshot], [proposal], model="test")


@pytest.mark.parametrize(
    ("claim", "cards", "required_error", "expected"),
    [
        (_claim(checkability="not_checkable"), [], False, "not_checkable"),
        (_claim(), [], True, "verification_error"),
        (
            _claim(),
            [_card(stance="supports"), _card(stance="contradicts", evidence_id="e2")],
            False,
            "mixed_evidence",
        ),
        (_claim(), [_card(stance="contradicts")], False, "contradicted_by_evidence"),
        (
            _claim(),
            [_card(stance="supports", interested_party=True)],
            False,
            "supported_by_evidence",
        ),
        (
            _claim(kind="quantity"),
            [_card(stance="supports", interested_party=True)],
            False,
            "insufficient_evidence",
        ),
        (
            _claim(kind="event"),
            [
                _card(
                    stance="supports",
                    source_class="independent_reporting",
                    origin_key=None,
                )
            ],
            False,
            "insufficient_evidence",
        ),
        (
            _claim(kind="event"),
            [_card(stance="supports", source_class="competent_record")],
            False,
            "supported_by_evidence",
        ),
        (_claim(), [], False, "insufficient_evidence"),
    ],
)
def test_adjudication_truth_table(claim, cards, required_error, expected) -> None:
    result = adjudicate_claim(
        claim,
        cards,
        required_stage_error=required_error,
    )

    assert isinstance(result, AdjudicationResult)
    assert result.status == expected


class _AssessmentClient:
    model = "assessment-test"

    def __init__(self, *, invalid: bool = False):
        self.invalid = invalid
        self.calls = 0

    async def complete(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.invalid:
            return '{"assessments":[]}'
        payload = json.loads(
            kwargs["user"].split("UNTRUSTED_EVIDENCE_DATA_START\n", 1)[1].split(
                "\nUNTRUSTED_EVIDENCE_DATA_END", 1
            )[0]
        )
        return json.dumps(
            {
                "assessments": [
                    {
                        "candidate_id": candidate["candidate_id"],
                        "excerpt": "Product X version 2 was officially released on August 11.",
                        "source_class": "original",
                        "interested_party": True,
                        "stance": "supports",
                        "entity_match": "match",
                        "temporal_match": "match",
                        "quantity_match": "unknown",
                    }
                    for candidate in payload["candidates"]
                ]
            }
        )


class _RetryAssessmentClient(_AssessmentClient):
    def __init__(self, invalid_calls: int):
        super().__init__()
        self.invalid_calls = invalid_calls

    async def complete(self, **kwargs):  # type: ignore[no-untyped-def]
        if self.calls < self.invalid_calls:
            self.calls += 1
            return '{"assessments":[]}'
        return await super().complete(**kwargs)


class _PartialLocatorAssessmentClient(_AssessmentClient):
    async def complete(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        payload = json.loads(
            kwargs["user"].split("UNTRUSTED_EVIDENCE_DATA_START\n", 1)[1].split(
                "\nUNTRUSTED_EVIDENCE_DATA_END", 1
            )[0]
        )
        assessments = []
        for index, candidate in enumerate(payload["candidates"]):
            assessments.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "excerpt": (
                        "Product X version 2 was officially released on August 11."
                        if index == 0
                        else "This is a paraphrase that is absent from the document."
                    ),
                    "source_class": "original",
                    "interested_party": True,
                    "stance": "supports",
                    "entity_match": "match",
                    "temporal_match": "match",
                    "quantity_match": "unknown",
                }
            )
        return json.dumps({"assessments": assessments})


async def _empty_search(query: str, max_results: int) -> SearchOutcome:
    return SearchOutcome(query=query, status="ok")


def test_verifier_fetches_documents_not_snippets_and_supports_direct_release() -> None:
    client = _AssessmentClient()

    async def search(query: str, max_results: int) -> SearchOutcome:
        return SearchOutcome(
            query=query,
            status="ok",
            hits=(
                SearchHit(
                    discovery_id="snippet-only",
                    rank=1,
                    title="Snippet says false",
                    url="https://unavailable.example/story",
                    snippet="This snippet contradicts the claim but is not evidence.",
                ),
            ),
        )

    async def fetch(url: str) -> DocumentFetchOutcome:
        if "vendor.example" in url:
            return _fetch_outcome(
                url,
                b"Product X version 2 was officially released on August 11.",
            )
        return DocumentFetchOutcome(
            status="not_found",
            requested_url=url,
            final_url=url,
            http_status=404,
        )

    verifier = EvidenceVerifier(
        client,
        max_queries=3,
        max_documents=6,
        budget=ItemVerificationBudget(max_model_calls=5, used_model_calls=1),
        search=search,
        fetch=fetch,
    )

    result = asyncio.run(verifier.verify(_claim(), _selected()))

    assert result.adjudication.status == "supported_by_evidence"
    assert result.stop_reason == "sufficient"
    assert result.documents_fetched == 1
    assert len(result.evidence_cards) == 1
    assert "snippet" not in result.evidence_cards[0].excerpt.lower()
    assert result.search_outcomes[0]["hits"][0]["snippet"].startswith(
        "This snippet contradicts"
    )
    assert client.calls == 1


def test_verifier_retries_invalid_assessment_and_counts_budget() -> None:
    client = _RetryAssessmentClient(invalid_calls=1)
    budget = ItemVerificationBudget(max_model_calls=3)

    result = asyncio.run(
        EvidenceVerifier(
            client,
            max_queries=1,
            max_documents=2,
            budget=budget,
            search=_empty_search,
            fetch=lambda url: asyncio.sleep(
                0,
                result=_fetch_outcome(
                    url,
                    b"Product X version 2 was officially released on August 11.",
                ),
            ),
        ).verify(_claim(), _selected())
    )

    assert result.adjudication.status == "supported_by_evidence"
    assert result.model_calls == 2
    assert budget.used_model_calls == 2
    assert client.calls == 2


def test_verifier_discards_bad_excerpt_without_false_support() -> None:
    async def search(query: str, max_results: int) -> SearchOutcome:
        return SearchOutcome(
            query=query,
            status="ok",
            hits=(
                SearchHit(
                    discovery_id="second-source",
                    rank=1,
                    title="Second source",
                    url="https://other.example/release",
                    snippet="Not evidence",
                ),
            ),
        )

    async def fetch(url: str) -> DocumentFetchOutcome:
        content = (
            b"Product X version 2 was officially released on August 11."
            if "vendor.example" in url
            else b"A second document about the Product X release."
        )
        return _fetch_outcome(url, content)

    result = asyncio.run(
        EvidenceVerifier(
            _PartialLocatorAssessmentClient(),
            max_queries=1,
            max_documents=2,
            budget=ItemVerificationBudget(max_model_calls=5),
            search=search,
            fetch=fetch,
        ).verify(_claim(), _selected())
    )

    assert result.adjudication.status == "insufficient_evidence"
    assert result.adjudication.missing_gates == (
        "all_material_assessments_anchored",
    )
    assert len(result.evidence_cards) == 1
    assert result.discarded_assessment_count == 1
    assert result.report_dict()["discarded_assessment_count"] == 1


@pytest.mark.parametrize(
    ("search_outcome", "expected_status", "expected_stop"),
    [
        (SearchOutcome(query="q", status="ok"), "insufficient_evidence", "source_unavailable"),
        (
            SearchOutcome(
                query="q",
                status="error",
                error_code="rate_limited",
            ),
            "verification_error",
            "backend_error",
        ),
    ],
)
def test_verifier_distinguishes_healthy_empty_search_from_backend_error(
    search_outcome, expected_status, expected_stop
) -> None:
    async def search(query: str, max_results: int) -> SearchOutcome:
        return SearchOutcome(
            query=query,
            status=search_outcome.status,
            error_code=search_outcome.error_code,
        )

    async def unavailable(url: str) -> DocumentFetchOutcome:
        return DocumentFetchOutcome(
            status="not_found",
            requested_url=url,
            final_url=url,
            http_status=404,
        )

    result = asyncio.run(
        EvidenceVerifier(
            _AssessmentClient(),
            max_queries=1,
            max_documents=2,
            budget=ItemVerificationBudget(max_model_calls=5),
            search=search,
            fetch=unavailable,
        ).verify(_claim(), _selected())
    )

    assert result.adjudication.status == expected_status
    assert result.stop_reason == expected_stop
    assert result.evidence_cards == ()


def test_verifier_records_assessment_contract_failure_and_cache_reuse() -> None:
    fetch_calls = []

    async def fetch(url: str) -> DocumentFetchOutcome:
        fetch_calls.append(url)
        return _fetch_outcome(
            url,
            b"Product X version 2 was officially released on August 11.",
        )

    verifier = EvidenceVerifier(
        _AssessmentClient(invalid=True),
        max_queries=1,
        max_documents=2,
        budget=ItemVerificationBudget(max_model_calls=5),
        search=_empty_search,
        fetch=fetch,
    )
    first = asyncio.run(verifier.verify(_claim(), _selected()))
    second = asyncio.run(
        verifier.verify(_claim(claim_id="claim-2"), _selected())
    )

    assert first.adjudication.status == "verification_error"
    assert second.adjudication.status == "verification_error"
    assert second.cache_reuse == 1
    assert len(fetch_calls) == 1


def test_ledger_persists_evidence_cards_reports_and_exact_locators(tmp_path) -> None:
    item = ContentItem(
        id="rss:item-1",
        source_type=SourceType.RSS,
        title="Product X released",
        url="https://vendor.example/release",
        content="Product X version 2 was released on August 11.",
        published_at=NOW,
        fetched_at=NOW,
    )
    ledger = ShadowLedger.start(
        [item], root=tmp_path, run_id="run-evidence", captured_at=NOW
    )
    ledger.capture_selected(
        [item],
        url_dedup_members={item.id: [item.id]},
        topic_dedup_members={item.id: [item.id]},
        captured_at=NOW,
    )
    selected = ledger.selected_snapshots[0]
    claim = replace(_claim(), selected_input_snapshot_id=selected.snapshot_id)
    claim_outcome = ClaimExtractionOutcome(
        selected_input_snapshot_id=selected.snapshot_id,
        item_id=item.id,
        status="ok",
        claims=(claim,),
        model="test",
    )
    ledger.capture_claims([claim_outcome], captured_at=NOW)

    snapshot = build_evidence_snapshot(
        _fetch_outcome(
            "https://vendor.example/release",
            b"Product X version 2 was officially released on August 11.",
        ),
        retrieved_at=NOW,
    )
    assert snapshot is not None
    proposal = EvidenceAssessmentProposal(
        candidate_id=snapshot.snapshot_id,
        excerpt="Product X version 2 was officially released on August 11.",
        source_class="original",
        interested_party=True,
        stance="supports",
        entity_match="match",
        temporal_match="match",
        quantity_match="unknown",
    )
    card = anchor_evidence_assessments(
        claim, [snapshot], [proposal], model="test"
    )[0]
    result = ClaimVerificationResult(
        claim=claim,
        adjudication=adjudicate_claim(claim, [card]),
        evidence_snapshots=(snapshot,),
        evidence_cards=(card,),
        stop_reason="sufficient",
        search_calls=1,
        documents_attempted=1,
        documents_fetched=1,
        cache_reuse=0,
        model_calls=1,
    )
    report = build_verification_report(
        run_id=ledger.run_id,
        selected_snapshot=selected,
        claim_outcome=claim_outcome,
        claim_results=[result],
        artifacts={},
        created_at=NOW,
    )

    ledger.capture_verification([result], [report], captured_at=NOW)

    manifest = json.loads(
        (ledger.run_dir / "manifest.json").read_text(encoding="utf-8")
    )
    evidence_lines = [
        json.loads(line)
        for line in (ledger.run_dir / "evidence.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    stored_card = next(line for line in evidence_lines if line["record_type"] == "card")
    stored_snapshot = next(
        line for line in evidence_lines if line["record_type"] == "snapshot"
    )
    report_path = ledger.run_dir / "reports" / f"{report['report_id']}.json"

    assert manifest["stage"] == "evidence"
    assert report_path.exists()
    assert stored_snapshot["normalized_text"][
        stored_card["excerpt_start"] : stored_card["excerpt_end"]
    ] == stored_card["excerpt"]
    object_path = (
        tmp_path
        / "objects"
        / "sha256"
        / snapshot.normalized_object_hash[:2]
        / snapshot.normalized_object_hash
    )
    assert object_path.read_text(encoding="utf-8") == snapshot.normalized_text


def test_ledger_reuses_same_document_fetched_at_different_times(tmp_path) -> None:
    item = ContentItem(
        id="rss:item-1",
        source_type=SourceType.RSS,
        title="Product X released",
        url="https://vendor.example/release",
        content="Product X version 2 was released on August 11.",
        published_at=NOW,
        fetched_at=NOW,
    )
    ledger = ShadowLedger.start(
        [item], root=tmp_path, run_id="run-reused-evidence", captured_at=NOW
    )
    ledger.capture_selected(
        [item],
        url_dedup_members={item.id: [item.id]},
        topic_dedup_members={item.id: [item.id]},
        captured_at=NOW,
    )
    selected = ledger.selected_snapshots[0]
    first_claim = replace(_claim(), selected_input_snapshot_id=selected.snapshot_id)
    second_claim = replace(
        first_claim,
        claim_id="claim-2",
        normalized_claim="Product X release was independently reported",
    )
    claim_outcome = ClaimExtractionOutcome(
        selected_input_snapshot_id=selected.snapshot_id,
        item_id=item.id,
        status="ok",
        claims=(first_claim, second_claim),
        model="test",
    )
    ledger.capture_claims([claim_outcome], captured_at=NOW)

    first_snapshot = build_evidence_snapshot(
        _fetch_outcome(
            "https://vendor.example/release",
            b"Product X version 2 was officially released on August 11.",
        ),
        retrieved_at=NOW,
    )
    assert first_snapshot is not None
    second_snapshot = replace(
        first_snapshot,
        requested_url="https://search.example/redirect",
        retrieved_at=(NOW + timedelta(minutes=1)).isoformat(),
    )
    results = [
        ClaimVerificationResult(
            claim=claim,
            adjudication=adjudicate_claim(claim, []),
            evidence_snapshots=(snapshot,),
            evidence_cards=(),
            stop_reason="no_novelty",
            search_calls=1,
            documents_attempted=1,
            documents_fetched=1,
            cache_reuse=0,
        )
        for claim, snapshot in (
            (first_claim, first_snapshot),
            (second_claim, second_snapshot),
        )
    ]
    report = build_verification_report(
        run_id=ledger.run_id,
        selected_snapshot=selected,
        claim_outcome=claim_outcome,
        claim_results=results,
        artifacts={},
        created_at=NOW,
    )

    ledger.capture_verification(results, [report], captured_at=NOW)

    snapshots = [
        json.loads(line)
        for line in (ledger.run_dir / "evidence.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if '"record_type":"snapshot"' in line
    ]
    assert len(snapshots) == 1
    assert snapshots[0]["retrieved_at"] == first_snapshot.retrieved_at
