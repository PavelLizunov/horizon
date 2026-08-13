"""Print a compact status summary for the latest Evidence Ledger run."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from src._file_utils import _atomic_write_text
from src.ai.summarizer import (
    _escape_markdown,
    _safe_url,
    verification_site_markup,
    verification_summary_markup,
)


def _runs(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    runs = []
    for run_dir in sorted(root.iterdir(), key=lambda path: path.name, reverse=True):
        manifest_path = run_dir / "manifest.json"
        if not run_dir.is_dir() or not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        runs.append((run_dir, manifest))
    return runs


def summarize(root: Path) -> dict[str, Any]:
    runs = _runs(root)

    if not runs:
        raise FileNotFoundError(f"no Evidence Ledger runs found under {root}")

    latest_dir, latest = runs[0]
    complete = next(
        (
            (run_dir, manifest)
            for run_dir, manifest in runs
            if manifest.get("stage") == "evidence"
        ),
        None,
    )
    result: dict[str, Any] = {
        "latest_attempt": {
            "run_id": latest.get("run_id", latest_dir.name),
            "stage": latest.get("stage", "unknown"),
            "updated_at": latest.get("updated_at"),
        },
        "complete_run": None,
    }
    if complete is None:
        return result

    run_dir, manifest = complete
    verdicts: Counter[str] = Counter()
    audits: Counter[str] = Counter()
    models: set[str] = set()
    search_errors = 0
    fetch_errors = 0
    unchecked_spans = 0
    report_count = 0
    report_errors = 0
    for report_path in sorted((run_dir / "reports").glob("*.json")):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report_errors += 1
            continue
        report_count += 1
        verdicts.update(report.get("status_by_claim", {}).values())
        if report.get("assessment_model"):
            models.add(report["assessment_model"])
        audit = report.get("artifact_audit") or {}
        audits[audit.get("status", "missing")] += 1
        unchecked_spans += int(audit.get("unchecked_span_count", 0))
        for claim in report.get("claim_results", []):
            search_errors += len(claim.get("search_errors", []))
            fetch_errors += len(claim.get("fetch_errors", []))

    result["complete_run"] = {
        "run_id": manifest.get("run_id", run_dir.name),
        "updated_at": manifest.get("updated_at"),
        "selected_items": manifest.get("selected_snapshot_count", 0),
        "claims": manifest.get("claim_count", 0),
        "discarded_claims": sum(
            outcome.get("discarded_claim_count", 0)
            for outcome in manifest.get("claim_extraction", [])
        ),
        "reports": report_count,
        "report_errors": report_errors,
        "verdicts": dict(sorted(verdicts.items())),
        "artifact_audits": dict(sorted(audits.items())),
        "unchecked_factual_spans": unchecked_spans,
        "search_errors": search_errors,
        "fetch_errors": fetch_errors,
        "models": sorted(models),
    }
    return result


def build_site_page(root: Path) -> str:
    """Render the latest complete ledger as a reader-facing Russian page."""
    complete = next(
        (
            (run_dir, manifest)
            for run_dir, manifest in _runs(root)
            if manifest.get("stage") == "evidence" and manifest.get("reports")
        ),
        None,
    )
    if complete is None:
        return "# Проверка новостей\n\nЗавершённых проверок пока нет.\n"

    run_dir, manifest = complete
    input_rows = [
        json.loads(line)
        for line in (run_dir / manifest["input_ledger"])
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    selected = {
        row["item_id"]: row["payload"]
        for row in input_rows
        if row.get("snapshot_type") == "selected"
    }
    claims = {
        row["claim_id"]: row
        for row in (
            json.loads(line)
            for line in (run_dir / "claims.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    }
    evidence_rows = [
        json.loads(line)
        for line in (run_dir / "evidence.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    snapshots = {
        row["snapshot_id"]: row
        for row in evidence_rows
        if row.get("record_type") == "snapshot"
    }
    cards = {
        row["evidence_id"]: row
        for row in evidence_rows
        if row.get("record_type") == "card"
    }

    updated = str(manifest.get("updated_at") or "")[:10]
    lines = [
        "# Проверка новостей",
        "",
        "Экспериментальная проверка ключевых утверждений по открытым источникам. "
        "Это оценка найденных доказательств, а не безусловная метка истины.",
    ]
    if updated:
        lines += ["", f"Последнее обновление: {updated}."]

    for report_path in sorted((run_dir / "reports").glob("*.json")):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        item = selected.get(report.get("item_id"), {})
        title = _escape_markdown(
            item.get("title") or report.get("item_id") or "Материал"
        )
        url = _safe_url(item.get("url", ""))
        lines += ["", f"## [{title}]({url})" if url else f"## {title}", ""]
        public_claims = []
        for claim_id, status in report.get("status_by_claim", {}).items():
            claim = claims.get(claim_id)
            if claim is None:
                continue
            sources = []
            seen_sources = set()
            for evidence_id in report.get("evidence_ids_by_claim", {}).get(
                claim_id, []
            ):
                card = cards.get(evidence_id)
                if card is None or card.get("stance") not in {
                    "supports",
                    "contradicts",
                    "context",
                }:
                    continue
                snapshot = snapshots.get(card.get("evidence_snapshot_id"))
                if snapshot is None:
                    continue
                source = (snapshot.get("final_url"), card["stance"])
                if source in seen_sources:
                    continue
                seen_sources.add(source)
                sources.append({"url": source[0], "stance": source[1]})
            public_claims.append(
                {
                    "text": claim["normalized_claim"],
                    "status": status,
                    "sources": sources,
                }
            )
        payload = {
            "state": "checked",
            "claims": public_claims,
            "token_usage": report.get("token_usage"),
        }
        summary_markup = verification_summary_markup(payload, "ru")
        markup = verification_site_markup(
            payload,
            "ru",
            heading_level=3,
            include_note=False,
        )
        if summary_markup:
            lines.append(summary_markup)
        if markup:
            lines.append(markup)
    return "\n".join(lines).rstrip() + "\n"


def format_summary(summary: dict[str, Any]) -> str:
    latest = summary["latest_attempt"]
    lines = [
        "Evidence Ledger status",
        f"Latest attempt: {latest['run_id']} — {latest['stage']}",
    ]
    complete = summary["complete_run"]
    if complete is None:
        lines.append("No complete evidence run yet.")
        return "\n".join(lines)

    lines.extend(
        [
            f"Last complete run: {complete['run_id']}",
            f"Items / reports: {complete['selected_items']} / {complete['reports']}",
            (
                f"Claims: {complete['claims']} "
                f"(discarded proposals: {complete['discarded_claims']})"
            ),
            "Verdicts: "
            + ", ".join(
                f"{name}={count}" for name, count in complete["verdicts"].items()
            ),
            "Artifact audits: "
            + ", ".join(
                f"{name}={count}"
                for name, count in complete["artifact_audits"].items()
            ),
            f"Unchecked factual spans: {complete['unchecked_factual_spans']}",
            (
                f"Search / fetch errors: {complete['search_errors']} / "
                f"{complete['fetch_errors']}"
            ),
            f"Unreadable reports: {complete['report_errors']}",
            "Model: " + ", ".join(complete["models"]),
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/verification/runs"),
        help="Evidence Ledger runs directory",
    )
    parser.add_argument(
        "--json", action="store_true", help="print machine-readable JSON"
    )
    parser.add_argument(
        "--write-site",
        type=Path,
        help="write the latest complete run as a public Markdown page",
    )
    args = parser.parse_args()
    if args.write_site:
        _atomic_write_text(args.write_site, build_site_page(args.root))
        print(f"Wrote verification page: {args.write_site}")
        return
    summary = summarize(args.root)
    print(
        json.dumps(summary, ensure_ascii=False, indent=2)
        if args.json
        else format_summary(summary)
    )


if __name__ == "__main__":
    main()
