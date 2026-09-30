"""Pure frozen-digest parser shared by archive tools and site builds."""

import html
import re

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


