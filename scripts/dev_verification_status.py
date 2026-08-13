"""Print a compact status summary for the latest Evidence Ledger run."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any


def summarize(root: Path) -> dict[str, Any]:
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
    args = parser.parse_args()
    summary = summarize(args.root)
    print(
        json.dumps(summary, ensure_ascii=False, indent=2)
        if args.json
        else format_summary(summary)
    )


if __name__ == "__main__":
    main()
