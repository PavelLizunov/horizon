"""Backfill the search index from the saved digest archive (dev utility).

Runs of the pipeline index their own articles; this replays the history that
predates that. It parses `data/summaries/horizon-{date}-{lang}.md` — the
combined per-issue documents — into the same search documents a live run
produces, with the same issue-scoped ids, so a later live reindex overwrites
rather than duplicates.

    uv run python scripts/dev_reindex_archive.py            # index everything
    uv run python scripts/dev_reindex_archive.py --dry-run  # parse and print only
"""

import argparse
import asyncio
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv

from src.services.search import SearchIndexer
from src.storage.manager import StorageManager

SUMMARIES_DIR = Path("data/summaries")

_ANCHOR_RE = re.compile(r'<a id="(item-[^"]+)"></a>')
_HEADING_RE = re.compile(r"^###\s+\[(?P<title>.*)\]\((?P<url>[^)]*)\)\s+⭐️\s+(?P<score>[\d.]+)")
_DETAILS_RE = re.compile(r"<details>.*?</details>", re.S)
_TAGS_RE = re.compile(r"^\*\*[^*]+\*\*:\s*(`[^`]*`(, )?)+\s*$", re.M)
_BLOCK_TITLE_RE = re.compile(r"\*\*「([^」]+)」\*\*\s*")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def _plain(markdown: str) -> str:
    text = _DETAILS_RE.sub(" ", markdown)
    text = _TAGS_RE.sub(" ", text)
    text = _BLOCK_TITLE_RE.sub(r"\1: ", text)
    text = _MD_LINK_RE.sub(r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_summary(markdown: str, date: str, language: str) -> list[dict]:
    """Split one combined issue document into per-article search documents."""
    anchors = list(_ANCHOR_RE.finditer(markdown))
    documents = []
    for position, match in enumerate(anchors):
        anchor = match.group(1)
        end = anchors[position + 1].start() if position + 1 < len(anchors) else len(markdown)
        segment = markdown[match.end() : end]
        heading = _HEADING_RE.match(segment.lstrip("\n"))
        if not heading:
            continue  # unparseable item: skip loudly? no — the archive is frozen, skip
        documents.append(
            {
                "id": f"{date}-{language}-{anchor.removeprefix('item-')}",
                "title": heading.group("title").replace("\\", ""),
                "content": _plain(segment),
                "url": heading.group("url"),
                "date": date,
                "language": language,
                "profile": re.match(r"item-(.+)-\d+$", anchor).group(1),
                "score": float(heading.group("score")),
            }
        )
    return documents


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="parse and print, do not index")
    parser.add_argument("--url", help="Elasticsearch URL (default: config search.url)")
    parser.add_argument("--index", help="index name (default: config search.index)")
    args = parser.parse_args()

    load_dotenv()
    config = StorageManager().load_config()
    url = args.url or config.search.url
    index = args.index or config.search.index

    total = 0
    batches: list[tuple[str, str, list[dict]]] = []
    for path in sorted(SUMMARIES_DIR.glob("horizon-*.md")):
        stem = path.name[len("horizon-") : -len(".md")]
        date, _, language = stem.rpartition("-")
        documents = parse_summary(path.read_text(encoding="utf-8"), date, language)
        print(f"{path.name}: {len(documents)} articles")
        total += len(documents)
        batches.append((date, language, documents))

    if args.dry_run:
        for _, _, documents in batches:
            for doc in documents:
                print(f"  {doc['id']}  ⭐️ {doc['score']}  {doc['title'][:60]}")
        print(f"dry run: {total} documents, nothing indexed")
        return

    async with SearchIndexer(
        config.search.model_copy(update={"url": url, "index": index}),
        client=httpx.AsyncClient(base_url=url, timeout=60),
    ) as indexer:
        await indexer.ensure_index()
        for _, _, documents in batches:
            await indexer.index_documents(documents)
    print(f"indexed {total} documents into {index} at {url}")


if __name__ == "__main__":
    asyncio.run(main())
