from __future__ import annotations

import json

from scripts.dev_verification_status import build_site_page, format_summary, summarize


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


def test_site_page_uses_public_claims_statuses_and_source_links(tmp_path) -> None:
    run = tmp_path / "20260813T090000-complete"
    run.joinpath("reports").mkdir(parents=True)
    run.joinpath("inputs").mkdir()
    run.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "run_id": run.name,
                "stage": "evidence",
                "updated_at": "2026-08-13T09:30:00Z",
                "input_ledger": "inputs/items.jsonl",
                "reports": {"one": "unused-in-fixture"},
            }
        ),
        encoding="utf-8",
    )
    run.joinpath("inputs", "items.jsonl").write_text(
        json.dumps(
            {
                "item_id": "item-1",
                "snapshot_type": "selected",
                "payload": {
                    "title": "Release <X>",
                    "url": "https://news.example/release?q=1&lang=ru",
                },
            }
        ),
        encoding="utf-8",
    )
    run.joinpath("claims.jsonl").write_text(
        json.dumps(
            {"claim_id": "claim-1", "normalized_claim": "Version 2 released"}
        ),
        encoding="utf-8",
    )
    run.joinpath("evidence.jsonl").write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {
                    "record_type": "snapshot",
                    "snapshot_id": "snapshot-1",
                    "final_url": "https://source.example/proof",
                    "normalized_text": "private ledger copy",
                },
                {
                    "record_type": "card",
                    "evidence_id": "evidence-1",
                    "evidence_snapshot_id": "snapshot-1",
                    "stance": "supports",
                    "excerpt": "private excerpt",
                },
            )
        ),
        encoding="utf-8",
    )
    run.joinpath("reports", "one.json").write_text(
        json.dumps(
            {
                "item_id": "item-1",
                "status_by_claim": {"claim-1": "supported_by_evidence"},
                "evidence_ids_by_claim": {"claim-1": ["evidence-1"]},
                "token_usage": {
                    "model": "deepseek-v4-flash",
                    "input_tokens": 1_000,
                    "output_tokens": 200,
                    "total_tokens": 1_200,
                    "estimated_cost_usd": 0.00028,
                },
            }
        ),
        encoding="utf-8",
    )
    empty = tmp_path / "20260813T100000-empty"
    empty.mkdir()
    empty.joinpath("manifest.json").write_text(
        json.dumps({"stage": "evidence", "reports": {}}),
        encoding="utf-8",
    )

    page = build_site_page(tmp_path)

    assert "# Проверка новостей" in page
    assert "Release &lt;X&gt;" in page
    assert "Поддерживается указанными источниками" in page
    assert 'href="https://source.example/proof"' in page
    assert "1 200 токенов проверки (вход 1 000 / выход 200)" in page
    assert "≈ $0.000280 по тарифу API" in page
    assert "private ledger copy" not in page
    assert "private excerpt" not in page
