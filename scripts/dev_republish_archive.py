"""Republish the frozen archive as per-article site pages (dev utility).

Runs before per-article publishing existed produced one combined page per
issue; the site index now lists issue directories only. This rebuilds the
old issues in the current shape from `data/summaries/`, reusing the archive
parser so ids match what `dev_reindex_archive.py` indexed. Old combined
files are left in place: Telegram messages of those days still deep-link
into their anchors.

    uv run python scripts/dev_republish_archive.py
"""

import argparse
from pathlib import Path

from dotenv import load_dotenv

try:  # runnable both as `python scripts/...` and as a package import
    from scripts.dev_reindex_archive import SUMMARIES_DIR, parse_summary
except ImportError:
    from dev_reindex_archive import SUMMARIES_DIR, parse_summary

from src.ai.summarizer import (
    DEFAULT_BRAND,
    LABELS,
    ArticlePage,
    _issue_item_markup,
    _pager_markup,
    article_site_markup,
)
from src.storage.manager import StorageManager


def render_page(doc: dict) -> ArticlePage:
    # id = {date}-{language}-{slug}; the slug is the anchor minus its prefix,
    # the same derivation the live publisher uses.
    slug = doc["id"].removeprefix(f"{doc['date']}-{doc['language']}-")
    # Emit the score and the source link in the same bare form the live
    # renderer produces, and let article_site_markup restructure both. Building
    # the finished markup here meant this script silently kept the previous
    # design's shape: the regexes look for the renderer's form and never saw it.
    lines = [
        f'<a id="item-{slug}"></a>',
        f'# [{doc["title"]}]({doc["url"]}) \u2b50\ufe0f {doc["score"]:.1f}/10',
        "",
        doc["lead"],
        "",
        # Frozen summaries lose the original byline, so rebuild the part that
        # survives. The leading source type and the profile are dropped again
        # downstream \u2014 the profile becomes an icon chip, and "archive" names
        # our plumbing rather than anything the reader can go and read.
        f'{doc.get("source_type", "archive")} \u00b7 {doc["profile"]} \u00b7 {doc["date"]}',
    ]
    for title, text in doc["blocks"]:
        if text:
            lines += ["", f"## {title}", "", text]
    labels = LABELS.get(doc["language"], LABELS["en"])
    if doc.get("tags"):
        # Emitted in the renderer's own shape so article_site_markup turns it
        # into ul.hz-tags, the same path a live run takes.
        tags = ", ".join(f"`#{tag}`" for tag in doc["tags"])
        lines += ["", f"**{labels['tags']}**: {tags}"]
    return ArticlePage(
        slug=slug,
        title=doc["title"],
        markdown=article_site_markup(
            "\n".join(lines) + "\n",
            profile_id=doc["profile"],
            issue_date=doc["date"],
        )
        + _pager_markup(labels["issue"]),
    )


def _render_issue_index(date: str, documents: list[dict]) -> ArticlePage:
    """The issue's index page, mirroring build_article_pages' listing."""
    lines: list[str] = [f"# {DEFAULT_BRAND} - {date}", ""]
    current_profile = None
    for doc in documents:
        if doc["profile"] != current_profile:
            if current_profile is not None:
                lines += ["</ul>", ""]
            current_profile = doc["profile"]
            lines += [f"## {current_profile}", "", '<ul class="hz-list">']
        slug = doc["id"].removeprefix(f"{doc['date']}-{doc['language']}-")
        lines.append(
            _issue_item_markup(slug, doc["title"], doc["score"], doc["url"])
        )
    if current_profile is not None:
        lines.append("</ul>")
    return ArticlePage(
        slug="index",
        title=f"{DEFAULT_BRAND} - {date}",
        markdown="\n".join(lines).rstrip() + "\n",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    storage = StorageManager()

    for path in sorted(SUMMARIES_DIR.glob("horizon-*.md")):
        stem = path.name[len("horizon-") : -len(".md")]
        date, _, language = stem.rpartition("-")
        documents = parse_summary(path.read_text(encoding="utf-8"), date, language)
        pages = [render_page(doc) for doc in documents]
        pages.append(_render_issue_index(date, documents))
        if args.dry_run:
            print(f"{path.name}: {len(pages)} pages (dry run)")
            continue
        issue_dir = storage.publish_site_pages(date, pages, language=language)
        print(f"{path.name}: {len(pages)} pages -> {issue_dir}")


if __name__ == "__main__":
    main()
