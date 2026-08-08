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
import html
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
    # The frozen archive predates the escaping fix and carries &#x27;-style
    # entities; search text should be the words, not the entities.
    text = html.unescape(text)
    # Drop the rendered-page chrome that is noise in search snippets: the
    ### heading line, the byline, and markdown backslash escapes.
    text = re.sub(r"(?m)^#{1,6} .*$", " ", text)
    text = "\n".join(
        line for line in text.split("\n") if not (" · " in line and "…" not in line and not line.rstrip().endswith("."))
    )
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _paragraphs(text: str) -> str:
    """Drop the byline line and collapse whitespace, keep paragraph breaks."""
    text = _MD_LINK_RE.sub(r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    kept = [
        line
        for line in text.split("\n")
        if not (" · " in line and not line.rstrip().endswith("."))
    ]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def _split_blocks(segment: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    """Lead paragraphs, (block title, block text) pairs, and tags of one item.

    Tags used to be dropped here along with the rest of the chrome. They are
    real model output, though, and republishing is the only way they reach the
    site for a frozen issue — so the archive rendered no tags at all while the
    stylesheet carried a tag component nothing ever used.
    """
    body = "\n".join(segment.lstrip("\n").split("\n")[1:])
    body = _DETAILS_RE.sub(" ", body)
    tags = [
        html.unescape(tag).replace("\\", "").lstrip("#")
        for match in _TAGS_RE.finditer(body)
        for tag in re.findall(r"`([^`]+)`", match.group(0))
    ]
    body = _TAGS_RE.sub(" ", body)
    parts = _BLOCK_TITLE_RE.split(body)
    lead = _paragraphs(parts[0])
    blocks = [
        (html.unescape(parts[i]), _paragraphs(parts[i + 1]))
        for i in range(1, len(parts) - 1, 2)
    ]
    return lead, blocks, tags


def parse_summary(
    markdown: str, date: str, language: str, page_base: str = "https://digest.ninitux.com/digest"
) -> list[dict]:
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
        lead, blocks, tags = _split_blocks(segment)
        slug = anchor.removeprefix("item-")
        documents.append(
            {
                "id": f"{date}-{language}-{slug}",
                "title": html.unescape(heading.group("title").replace("\\", "")),
                "content": _plain(segment),
                "lead": lead,
                "blocks": blocks,
                "tags": tags,
                "url": heading.group("url"),
                "page": f"{page_base}/{date}-{language}/{slug}/",
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
        documents = parse_summary(
            path.read_text(encoding="utf-8"), date, language, config.search.site_base
        )
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
