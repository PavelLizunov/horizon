from __future__ import annotations

import json

from scripts.dev_verification_status import format_summary, summarize


def test_status_uses_latest_complete_run_when_newer_attempt_is_partial(tmp_path) -> None:
    complete = tmp_path / "20260813T090000-complete"
    complete.joinpath("reports").mkdir(parents=True)
    complete.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "run_id": complete.name,
                "stage": "evidence",
                "selected_snapshot_count": 1,
                "claim_count": 2,
                "claim_extraction": [{"discarded_claim_count": 1}],
            }
        ),
        encoding="utf-8",
    )
    complete.joinpath("reports", "one.json").write_text(
        json.dumps(
            {
                "assessment_model": "test-model",
                "status_by_claim": {
                    "one": "supported_by_evidence",
                    "two": "insufficient_evidence",
                },
                "artifact_audit": {"status": "ok", "unchecked_span_count": 3},
                "claim_results": [
                    {"search_errors": [], "fetch_errors": ["blocked"]}
                ],
            }
        ),
        encoding="utf-8",
    )
    complete.joinpath("reports", "corrupt.json").write_text("{", encoding="utf-8")
    partial = tmp_path / "20260813T100000-partial"
    partial.mkdir()
    partial.joinpath("manifest.json").write_text(
        json.dumps({"run_id": partial.name, "stage": "claims"}),
        encoding="utf-8",
    )

    status = summarize(tmp_path)

    assert status["latest_attempt"]["run_id"] == partial.name
    assert status["complete_run"] == {
        "run_id": complete.name,
        "updated_at": None,
        "selected_items": 1,
        "claims": 2,
        "discarded_claims": 1,
        "reports": 1,
        "report_errors": 1,
        "verdicts": {
            "insufficient_evidence": 1,
            "supported_by_evidence": 1,
        },
        "artifact_audits": {"ok": 1},
        "unchecked_factual_spans": 3,
        "search_errors": 0,
        "fetch_errors": 1,
        "models": ["test-model"],
    }
    assert "Last complete run" in format_summary(status)
