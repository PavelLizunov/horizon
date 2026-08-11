"""Offline policy/adversarial regression harness for Evidence Ledger."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .audit import ArtifactField, FactualSpanProposal, anchor_factual_spans
from .claims import ClaimCard
from .evidence import (
    AdjudicationResult,
    ClaimVerificationResult,
    EvidenceCard,
    adjudicate_claim,
)


@dataclass(frozen=True)
class EvaluationSummary:
    total_cases: int
    passed_cases: int
    false_supported: int
    failures: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "false_supported": self.false_supported,
            "failures": list(self.failures),
        }


def run_adversarial_evaluation(path: Path) -> EvaluationSummary:
    cases = json.loads(path.read_text(encoding="utf-8"))
    failures = []
    false_supported = 0
    for case in cases:
        if case["type"] == "adjudication":
            actual = _run_adjudication_case(case)
            expected = case["expected_status"]
            if actual == "supported_by_evidence" and expected != actual:
                false_supported += 1
        elif case["type"] == "audit":
            actual = _run_audit_case(case)
            expected = case["expected_unchecked"]
        else:
            actual = "unknown_case_type"
            expected = case.get("expected")
        if actual != expected:
            failures.append(
                {"id": case["id"], "expected": expected, "actual": actual}
            )
    return EvaluationSummary(
        total_cases=len(cases),
        passed_cases=len(cases) - len(failures),
        false_supported=false_supported,
        failures=tuple(failures),
    )


def _claim(data: dict[str, Any], claim_id: str = "claim-1") -> ClaimCard:
    text = data.get("text", "Product X version 2 was released")
    return ClaimCard(
        claim_id=claim_id,
        selected_input_snapshot_id="selected-1",
        source_field="title",
        source_start=0,
        source_end=len(text),
        source_text=text,
        normalized_claim=text,
        kind=data.get("kind", "release"),
        importance="headline",
        checkability=data.get("checkability", "checkable"),
    )


def _card(data: dict[str, Any], index: int) -> EvidenceCard:
    return EvidenceCard(
        evidence_id=f"evidence-{index}",
        claim_id="claim-1",
        evidence_snapshot_id=f"snapshot-{index}",
        excerpt_start=0,
        excerpt_end=8,
        excerpt="evidence",
        source_class=data.get("source_class", "original"),
        interested_party=data.get("interested_party", False),
        stance=data["stance"],
        entity_match=data.get("entity_match", "match"),
        temporal_match=data.get("temporal_match", "match"),
        quantity_match=data.get("quantity_match", "match"),
        origin_key=data.get("origin_key"),
        assessment_model="offline-fixture",
    )


def _run_adjudication_case(case: dict[str, Any]) -> str:
    claim = _claim(case.get("claim", {}))
    cards = [_card(value, index) for index, value in enumerate(case.get("cards", []))]
    return adjudicate_claim(
        claim,
        cards,
        required_stage_error=case.get("required_stage_error", False),
    ).status


def _run_audit_case(case: dict[str, Any]) -> int:
    fields = [ArtifactField(**value) for value in case["fields"]]
    claim_results = []
    for value in case.get("claim_results", []):
        claim = _claim(value, claim_id=value["claim_id"])
        claim_results.append(
            ClaimVerificationResult(
                claim=claim,
                adjudication=AdjudicationResult(status=value["status"]),
                evidence_snapshots=(),
                evidence_cards=(),
                stop_reason=(
                    "backend_error"
                    if value["status"] == "verification_error"
                    else "sufficient"
                ),
                search_calls=0,
                documents_attempted=0,
                documents_fetched=0,
                cache_reuse=0,
            )
        )
    proposals = [
        FactualSpanProposal.model_validate(value) for value in case["proposals"]
    ]
    spans = anchor_factual_spans(fields, proposals, claim_results)
    return sum(span.matched_claim_id is None for span in spans)
