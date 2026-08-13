"""Print a compact status summary for the latest Evidence Ledger run."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import html
import json
from pathlib import Path
import re
from typing import Any

from src._file_utils import _atomic_write_text
from src.ai.summarizer import (
    _escape_markdown,
    _safe_url,
    _VERIFICATION_COPY,
    verification_site_markup,
    verification_summary_markup,
)
from src.verification.evidence import public_claim_status
from src.verification.claims import conservative_claim_kind


_PUBLIC_CLAIM_RE = re.compile(
    r'(?P<open><li class="hz-verification__claim" data-status="(?P<status>[^"]+)" '
    r'data-raw-status="(?P<raw>[^"]+)">\n)'
    r'<span class="hz-verification__status">(?P<label>.*?)</span>\n'
    r'<p>(?P<claim>.*?)</p>',
    re.DOTALL,
)
_PUBLIC_COUNTS_RE = re.compile(r"<span>Утверждений: .*?</span>")


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


def _incident_lines(root: Path) -> list[str]:
    data_root = (
        root.parent.parent
        if root.name == "runs" and root.parent.name == "verification"
        else root
    )
    path = data_root / "incidents.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    incidents = payload.get("incidents")
    if not isinstance(incidents, dict) or not incidents:
        return []
    state_labels = {
        "PROVISIONAL": "предварительно",
        "CORROBORATED": "событие подтверждено источниками",
        "DISPUTED": "источники расходятся",
        "RESOLVED": "инцидент завершён",
    }
    rows = sorted(
        (row for row in incidents.values() if isinstance(row, dict)),
        key=lambda row: str(row.get("last_seen_at") or ""),
        reverse=True,
    )[:20]
    lines = [
        "",
        "## Наблюдаемые VPN- и сетевые инциденты",
        "",
        "Состояния меняются только при появлении новых источников; "
        "«предварительно» не означает подтверждение события.",
    ]
    for row in rows:
        claim = _escape_markdown(str(row.get("claim") or "Без описания"))
        state = state_labels.get(str(row.get("state") or ""), "неизвестно")
        lines += ["", f"- **{state}** — {claim}"]
        meta = []
        if row.get("first_seen_at"):
            meta.append(f"впервые: {str(row['first_seen_at'])[:16]}")
        if row.get("last_checked_at"):
            meta.append(f"проверено: {str(row['last_checked_at'])[:16]}")
        if row.get("next_check_at"):
            meta.append(f"следующая точка: {str(row['next_check_at'])[:16]}")
        if meta:
            lines.append(f"  {' · '.join(meta)}")
        urls = row.get("source_urls")
        if isinstance(urls, list):
            links = []
            for index, value in enumerate(urls[-3:], start=1):
                safe = _safe_url(value)
                if safe:
                    links.append(f"[источник {index}]({safe})")
            if links:
                lines.append(f"  {' · '.join(links)}")
    return lines


def sanitize_article_verification(
    markdown: str,
    language: str = "ru",
    claim_texts: dict[str, str] | None = None,
) -> str:
    """Refresh deterministic labels and restore exact public claim wording."""
    language_root = language.lower().replace("_", "-").partition("-")[0]
    copy = _VERIFICATION_COPY.get(language_root, _VERIFICATION_COPY["en"])

    def replace_claim(match: re.Match[str]) -> str:
        status = match.group("status")
        claim = html.unescape(match.group("claim"))
        public_claim = (claim_texts or {}).get(claim, claim)
        kind = None
        if match.group("raw") == "supported_by_evidence":
            action_kind = conservative_claim_kind("announcement", claim, claim)
            if action_kind in {"announcement", "release"}:
                kind = action_kind
            elif status in {"official_announcement", "official_release"}:
                kind = conservative_claim_kind(
                    (
                        "announcement"
                        if status == "official_announcement"
                        else "release"
                    ),
                    claim,
                    claim,
                )
        new_status = (
            public_claim_status(kind, match.group("raw"), None)
            if kind is not None
            else status
        )
        if new_status == status and public_claim == claim:
            return match.group(0)
        opening = match.group("open").replace(
            f'data-status="{status}"', f'data-status="{new_status}"'
        )
        label = copy["statuses"].get(new_status, copy["statuses"]["check_error"])
        return (
            opening
            + f'<span class="hz-verification__status">{label}</span>\n'
            + f'<p>{html.escape(public_claim)}</p>'
        )

    updated = _PUBLIC_CLAIM_RE.sub(replace_claim, markdown)
    matches = list(_PUBLIC_CLAIM_RE.finditer(updated))
    if language_root == "ru" and matches:
        counts = Counter(match.group("status") for match in matches)
        parts = [
            f'{copy["statuses"].get(status, copy["statuses"]["check_error"])}: {count}'
            for status, count in counts.items()
        ]
        count_markup = f'<span>Утверждений: {len(matches)} · {" · ".join(parts)}</span>'
        updated = _PUBLIC_COUNTS_RE.sub(count_markup, updated, count=1)
    return updated


def _latest_claim_texts(root: Path) -> dict[str, str]:
    """Map unambiguous normalized claims to their exact article spans."""
    complete = next(
        (
            run_dir
            for run_dir, manifest in _runs(root)
            if manifest.get("stage") == "evidence"
            and (run_dir / "claims.jsonl").exists()
        ),
        None,
    )
    if complete is None:
        return {}
    candidates: dict[str, set[str]] = {}
    for line in (complete / "claims.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            claim = json.loads(line)
        except json.JSONDecodeError:
            continue
        normalized = str(claim.get("normalized_claim") or "").strip()
        source = str(claim.get("source_text") or "").strip()
        if normalized and source and normalized != source:
            candidates.setdefault(normalized, set()).add(source)
    return {
        normalized: next(iter(sources))
        for normalized, sources in candidates.items()
        if len(sources) == 1
    }


def refresh_article_pages(
    root: Path,
    language: str = "ru",
    claim_texts: dict[str, str] | None = None,
) -> int:
    changed = 0
    for path in sorted(root.rglob("*.md")):
        if path.name == "index.md":
            continue
        before = path.read_text(encoding="utf-8")
        after = sanitize_article_verification(before, language, claim_texts)
        if after != before:
            _atomic_write_text(path, after)
            changed += 1
    return changed


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
        return "# Покрытие новостей источниками\n\nЗавершённых проверок пока нет.\n"

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
        "# Покрытие новостей источниками",
        "",
        "Проверка выбранных ключевых утверждений по открытым источникам. "
        "Это карта покрытия источниками, а не метка истинности всей статьи.",
    ]
    if updated:
        lines += ["", f"Последнее обновление: {updated}."]
    lines.extend(_incident_lines(root))
    lines += ["", "## Последняя выборка"]

    for report_path in sorted((run_dir / "reports").glob("*.json")):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        item = selected.get(report.get("item_id"), {})
        title = _escape_markdown(
            item.get("title") or report.get("item_id") or "Материал"
        )
        url = _safe_url(item.get("url", ""))
        lines += ["", f"### [{title}]({url})" if url else f"### {title}", ""]
        checked_at = str(report.get("created_at") or manifest.get("updated_at") or "")
        published_at = item.get("published_at")
        age_hours = None
        published = None
        checked = None
        try:
            if isinstance(published_at, str) and checked_at:
                published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
                age_hours = max((checked - published).total_seconds() / 3600, 0)
        except ValueError:
            published = checked = None
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
                sources.append(
                    {
                        "url": source[0],
                        "stance": source[1],
                        "source_class": card.get("source_class"),
                    }
                )
            kind = conservative_claim_kind(
                str(claim.get("kind") or "other"),
                str(claim.get("source_text") or ""),
                str(claim.get("normalized_claim") or ""),
            )
            public_claims.append(
                {
                    "text": claim.get("source_text") or claim["normalized_claim"],
                    "kind": kind,
                    "status": status,
                    "public_status": public_claim_status(kind, status, age_hours),
                    "sources": sources,
                }
            )
        statuses = set(report.get("status_by_claim", {}).values())
        audit = report.get("artifact_audit") or {}
        unchecked = sum(
            len(values)
            for values in (report.get("unchecked_factual_spans") or {}).values()
            if isinstance(values, list)
        )
        public_statuses = {claim["public_status"] for claim in public_claims}
        if (
            report.get("verification_error")
            or "verification_error" in statuses
            or audit.get("status") == "error"
        ):
            state = "check_error"
        elif not public_claims:
            state = "not_applicable"
        elif unchecked:
            state = "partial"
        elif public_statuses and public_statuses <= {
            "anecdotal",
            "not_applicable",
        }:
            state = "not_applicable"
        elif "provisional" in public_statuses and public_statuses <= {
            "provisional",
            "official_announcement",
            "official_release",
            "attributed_quote",
            "corroborated_event",
            "source_documented_quantity",
            "source_supported",
        }:
            state = "provisional"
        elif statuses & {"insufficient_evidence", "not_checkable"}:
            state = "partial"
        else:
            state = "complete"
        payload = {
            "state": state,
            "claims": public_claims,
            "token_usage": report.get("token_usage"),
            "checked_at": checked_at,
        }
        if age_hours is not None:
            payload["source_age_hours"] = round(age_hours, 1)
        if published is not None and checked is not None and any(
            claim.get("kind") in {"event", "other"}
            and claim.get("status")
            not in {"supported_by_evidence", "contradicted_by_evidence"}
            for claim in public_claims
        ):
            for delta in (timedelta(hours=24), timedelta(hours=72)):
                candidate = published + delta
                if checked < candidate:
                    payload["next_check_at"] = (
                        candidate.astimezone(timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z")
                    )
                    break
        summary_markup = verification_summary_markup(payload, "ru")
        markup = verification_site_markup(
            payload,
            "ru",
            heading_level=4,
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
    parser.add_argument(
        "--refresh-articles",
        type=Path,
        help="refresh deterministic verification labels in generated article pages",
    )
    args = parser.parse_args()
    if args.write_site:
        _atomic_write_text(args.write_site, build_site_page(args.root))
        print(f"Wrote verification page: {args.write_site}")
        return
    if args.refresh_articles:
        changed = refresh_article_pages(
            args.refresh_articles,
            claim_texts=_latest_claim_texts(args.root),
        )
        print(f"Refreshed verification labels in {changed} article pages")
        return
    summary = summarize(args.root)
    print(
        json.dumps(summary, ensure_ascii=False, indent=2)
        if args.json
        else format_summary(summary)
    )


if __name__ == "__main__":
    main()
