"""Daily summary generation — pure programmatic rendering."""

import html
import re
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import quote, urlsplit

from .localization import normalize_language
from ..models import ContentItem


_CJK = r"[\u4e00-\u9fff\u3400-\u4dbf]"
_ASCII = r"[A-Za-z0-9]"
# `<` and `>` are absent on purpose: html.escape has already turned them into
# entities by the time this runs. `|` is absent because Python-Markdown does not
# list it in ESCAPED_CHARS, so a backslash before it survives into the output as
# a literal backslash.
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#!])")
_MARKDOWN_BLOCK_START = re.compile(r"(?m)^( {0,3})(>|[-+] |\d+[.)] )")
_URL_SAFE_CHARS = ":/?#[]@!$&'*,;=~%+"


def _escape_markdown(value: object) -> str:
    """Render untrusted text literally while retaining its readable content.

    `quote=False` matters: with `quote=True` an apostrophe becomes the numeric
    reference `&#x27;`, and the very next line escapes the `#` *inside* that
    reference, producing the dead `&\\#x27;`. The named entities left by
    `quote=False` (`&amp;`, `&lt;`, `&gt;`) contain no character this regex
    touches. Callers use the result in document body context only — never in an
    HTML attribute — so dropping quote escaping is safe here; `_safe_url` and
    the reference titles keep `quote=True`.
    """
    escaped = html.escape(str(value), quote=False)
    escaped = _MARKDOWN_SPECIAL.sub(r"\\\1", escaped)
    return _MARKDOWN_BLOCK_START.sub(r"\1\\\2", escaped)


def _safe_url(value: object) -> Optional[str]:
    """Return an HTML/Markdown-safe HTTP(S) URL, or None for unsafe URLs."""
    raw = str(value).strip()
    if not raw or any(ord(char) < 32 or ord(char) == 127 for char in raw):
        return None
    try:
        parsed = urlsplit(raw)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None
        parsed.port
    except (TypeError, ValueError):
        return None
    encoded = quote(raw, safe=_URL_SAFE_CHARS)
    return html.escape(encoded, quote=True)


def _pangu(text: str) -> str:
    """Insert a space between CJK and ASCII letters/digits (Pangu spacing)."""
    text = re.sub(rf"({_CJK})({_ASCII})", r"\1 \2", text)
    text = re.sub(rf"({_ASCII})({_CJK})", r"\1 \2", text)
    return text


LABELS = {
    "en": {
        "header": "Horizon Daily",
        "source": "Source",
        "background": "Background",
        "discussion": "Discussion",
        "references": "References",
        "tags": "Tags",
        "issue": "All of this issue",
        "selected_items": "From {total} items, {selected} important content pieces were selected",
        "empty_analyzed": "Analyzed {total} items, but none met the importance threshold.",
        "empty_body": (
            "No significant developments today. This might indicate:\n"
            "- A quiet day in your tracked sources\n"
            "- The AI score threshold is too high\n"
            "- Your information sources need expansion\n\n"
            "Consider:\n"
            "1. Lowering the configured profile threshold\n"
            "2. Adding more diverse information sources\n"
            "3. Checking if the AI model is working correctly\n"
        ),
    },
    "zh": {
        "header": "Horizon 每日速递",
        "source": "来源",
        "background": "背景",
        "discussion": "社区讨论",
        "references": "参考链接",
        "tags": "标签",
        "issue": "查看本期全部内容",
        "selected_items": "从 {total} 条内容中筛选出 {selected} 条重要资讯。",
        "empty_analyzed": "已分析 {total} 条内容，但没有达到重要性阈值的条目。",
        "empty_body": (
            "今日暂无重要动态，可能原因：\n"
            "- 今天关注的信息源较平静\n"
            "- AI 评分阈值设置过高\n"
            "- 信息源种类有待扩充\n\n"
            "建议：\n"
            "1. 降低当前 Profile 的过滤阈值\n"
            "2. 添加更多多样化的信息源\n"
            "3. 检查 AI 模型是否正常工作\n"
        ),
    },
    "ru": {
        # Header stays the brand name; everything the reader sees around the
        # articles is Russian — the digest is written in ru, en fallback
        # labels ("References", "Tags") read as a bug on the site.
        "header": "Horizon Daily",
        "source": "Источник",
        "background": "Контекст",
        "discussion": "Обсуждение",
        "references": "Источники",
        "tags": "Теги",
        "issue": "Все материалы выпуска",
        "selected_items": "Из {total} материалов отобрано {selected} важных.",
        "empty_analyzed": "Проанализировано {total} материалов, но ни один не прошёл порог важности.",
        "empty_body": (
            "Сегодня без значимых событий. Возможные причины:\n"
            "- тихий день в отслеживаемых источниках\n"
            "- слишком высокий порог оценки\n"
            "- набор источников стоит расширить\n\n"
            "Что можно сделать:\n"
            "1. Понизить порог в настройках профиля\n"
            "2. Добавить больше источников\n"
            "3. Проверить, что модель оценки работает\n"
        ),
    },
}


@dataclass(frozen=True)
class ArticlePage:
    """One rendered page of the site: a single article, or an issue index."""

    slug: str
    title: str
    markdown: str


# CJK corner brackets around block titles, e.g. **「Контекст」**. Non-raw
# strings on purpose: re has no \u escape, the string parser resolves it.
_BLOCK_TITLE_RE = re.compile("(?m)^\\*\\*\u300c([^\u300d]+)\u300d\\*\\*[ \t]*")
_SCORE_IN_HEADING_RE = re.compile(" \u2b50\ufe0f ([0-9.]+|\\?)/10$")


_HEADING_LINK_RE = re.compile(r"^# \[(?P<title>.+)\]\((?P<url>\S*)\)\s*$")

# Citation ids the analyst leaves in its prose, e.g. "…6 августа 2026 [tool-2-1]".
# They name internal tool calls: the reader cannot follow them and the sources
# they stand for never reach the page. The leading space is part of the match so
# removing a run does not leave "года ." behind. Both the raw and the
# markdown-escaped shape are matched — summaries frozen in data/summaries/ were
# escaped before they were written, and republishing reads that text back.
_TOOL_TOKEN_RE = re.compile(r"[ \t]*(?:\\?\[tool-\d+-\d+\\?\])+")

# A tags line is recognised by its shape rather than its label, so this works for
# every language in LABELS without listing them.
_TAGS_LINE_RE = re.compile(r"(?m)^\*\*[^*]+\*\*: ((?:`#[^`]+`(?:, )?)+)\s*$")
_TAG_RE = re.compile(r"`#([^`]+)`")
_MARKDOWN_ESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#!>+.-])")
_INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\((\S+?)\)")

# Profiles differ by icon shape, never by colour — colour is spent on links.
_PROFILE_ICONS = {
    "tech-news": "news",
    "tech-blog": "blog",
    "video": "video",
    "finance-news": "finance",
}

# Internal plumbing names that used to open the byline. "rss" and "archive" tell
# a reader nothing about where the material came from; the source link does.
_INTERNAL_SOURCE_TOKENS = {"rss", "archive", "api", "web", "html", "unknown"}


def _strip_tool_tokens(text: str) -> str:
    return _TOOL_TOKEN_RE.sub("", text)


def _plain_text(value: str) -> str:
    """Undo markdown escaping for text about to be placed inside raw HTML.

    Inside an HTML block Python-Markdown does not process escapes, so a ``\\#``
    that reads correctly in markdown would render as a literal backslash.
    """
    return _MARKDOWN_ESCAPE_RE.sub(r"\1", value)


def _icon(name: str) -> str:
    return f'<span class="hz-i hz-i--{name}" aria-hidden="true"></span>'


def _byline_markup(
    text: str,
    source_url: Optional[str],
    profile_id: Optional[str],
    issue_date: Optional[str] = None,
) -> str:
    """Build the article byline: what kind, when, and a way to the original.

    The source link lives here rather than on the heading. With the title
    linked, a reader who clicked what looked like the article's own name left
    the site without ever seeing the analysis the page exists for.
    """
    parts = [part.strip() for part in text.split(" · ") if part.strip()]
    if parts and _plain_text(parts[0]).lower() in _INTERNAL_SOURCE_TOKENS:
        parts.pop(0)
    if profile_id:
        parts = [part for part in parts if _plain_text(part) != profile_id]
    if issue_date:
        # The crumb below already carries it; frozen bylines repeat it here.
        parts = [part for part in parts if _plain_text(part) != issue_date]

    chunks = []
    if issue_date:
        # The way back to the issue, on the first screen. The pager at the foot
        # of the page serves the reader who finished; this one serves the
        # reader who changed their mind, and who otherwise had three screens of
        # scrolling or the browser's back button.
        chunks.append(
            f'<a class="hz-crumb" href="../">{_icon("date")}'
            f"{html.escape(issue_date)}</a>"
        )
    if profile_id:
        icon = _icon(_PROFILE_ICONS.get(profile_id, "news"))
        chunks.append(
            f'<span class="hz-profile">{icon}{html.escape(profile_id)}</span>'
        )
    if parts:
        rest = _INLINE_LINK_RE.sub(
            r'<a href="\2">\1</a>', _plain_text(" · ".join(parts))
        )
        chunks.append(rest if issue_date else f"{_icon('date')}{rest}")
    if source_url:
        domain = urlsplit(source_url).netloc.removeprefix("www.")
        if domain:
            chunks.append(
                f'<a class="hz-source" href="{source_url}">'
                f"{html.escape(domain)}{_icon('external')}</a>"
            )
    return '<p class="hz-byline">' + "".join(chunks) + "</p>"


def _tags_markup(match: re.Match) -> str:
    """A ``**Tags**: `#a`, `#b``` line becomes the design system's tag list.

    The pill is attached to ``.hz-tag`` only. Styling ``code`` instead — the
    shape the renderer emits — would have caught every command and path the
    digest quotes in prose along with it.
    """
    items = "".join(
        f'<li><a class="hz-tag" href="/search/?q={quote(tag)}">'
        f"#{html.escape(tag)}</a></li>"
        for tag in (_plain_text(raw) for raw in _TAG_RE.findall(match.group(1)))
    )
    return f'<ul class="hz-tags">{items}</ul>' if items else ""


def _pager_markup(label: str) -> str:
    """The way out of an article page.

    Reaching the end of an article, the only way back was the browser's own
    back button — nothing on the page led anywhere. Neighbouring days are not
    linked from here: that needs knowledge of other issues this render does not
    have, and the archive is one click away in the nav.
    """
    return (
        '\n<nav class="hz-pager">'
        f'<a href="../">{html.escape(label)}{_icon("next")}</a>'
        "</nav>\n"
    )


def _score_tier(score: object) -> Optional[str]:
    """Ink step for a score, or None when there is no score to step.

    The thresholds came from the published issues rather than from taste:
    2026-08-07 ran 4.0…8.0 in whole points, so the first cut's 8.5 `high`
    never fired once and the whole issue rendered as mid and low.
    """
    try:
        value = float(score)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return "high" if value >= 8.0 else "mid" if value >= 6.0 else "low"


def _issue_item_markup(slug: str, title: str, score: object, url: object) -> str:
    """One row of an issue's article list (§13 of the design system).

    The list used to be ``- [title](slug.md) ⭐️ 8.0/10``. Seven identical stars
    were the only colour on an otherwise monochrome page, and they encoded
    nothing: a 4.0 and an 8.0 were set with exactly the same weight. The tier
    on the ``li`` is what lets the CSS mute the weak material as a whole rather
    than only its number.
    """
    tier = _score_tier(score)
    attribute = f' data-tier="{tier}"' if tier else ""
    domain = urlsplit(str(url)).netloc.removeprefix("www.")
    meta = f'<div class="hz-item__meta">{html.escape(domain)}</div>' if domain else ""
    return (
        f"<li{attribute}><div class=\"hz-item\">"
        f'<a class="hz-item__title" href="{slug}/">{html.escape(title)}</a>'
        f"{_score_markup(score, lead=False)}{meta}"
        f"</div></li>"
    )


def _score_markup(raw: object, *, lead: bool = True) -> str:
    """Render a score per the design system's markup contract (§12 of the CSS).

    The bare number said nothing — 9.0 and 4.0 were set identically. The CSS
    encodes it twice, both monochrome: an ink tier and a meter whose width is
    `--hz-score`.

    The meter is normalised to 4…10, the range the published issues actually
    occupy; the first cut's floor of 5 clipped a real 4.0 to nothing. Tiers are
    `_score_tier`'s.

    A missing score ("?") still gets the element so the layout does not jump,
    but with no tier and an empty meter.
    """
    classes = "hz-score hz-score--lead" if lead else "hz-score"
    tier = _score_tier(raw)
    if tier is None:
        return f'<span class="{classes}">{html.escape(str(raw))}</span>'

    value = float(raw)  # type: ignore[arg-type]
    fill = min(max((value - 4.0) / 6.0, 0.04), 1.0)
    scale = '<span class="hz-score__scale">/10</span>' if lead else ""
    return (
        f'<span class="{classes}" data-tier="{tier}" '
        f'style="--hz-score:{fill:.2f}">{raw}{scale}</span>'
    )


def article_site_markup(
    markdown: str,
    *,
    profile_id: Optional[str] = None,
    issue_date: Optional[str] = None,
) -> str:
    """Restructure a rendered item for its own site page. Site-only.

    The shared renderer emits one combined-document shape (bold-run block
    titles, score and source link glued to the heading, a trailing separator
    before the next item). On a standalone page each of those reads wrong, so
    the page gets restructured here instead of changing the renderer everyone
    else shares:

    - ``**"X"** body`` becomes an ``## X`` section heading plus its body, so
      labelled blocks are visually separate and land in the page TOC;
    - the heading keeps the title and nothing else. The score becomes a
      ``span.hz-score`` of its own, and the source link moves into the byline:
      with the title linked, a reader who clicked what looked like the
      article's own name left the site without seeing the analysis the page
      exists for;
    - the byline is rebuilt as ``p.hz-byline`` and moves *above* the lede. It
      used to sit under four sentences of summary, which put the reader well
      into the text before anything said where the text came from;
    - the lede is marked, so the entry to the text is distinct from the body;
    - tool citation ids, and the trailing ``---``, are dropped.

    Taking the score out of the heading also fixes the permalink: with it
    inline the anchor came out as ``#amd-taalas-8010``, so rescoring an
    article silently changed its own address.
    """
    markdown = _strip_tool_tokens(markdown)
    # Section headings. The block title may contain escaped markdown; it was
    # escaped for inline bold context, and heading context accepts the same.
    markdown = _BLOCK_TITLE_RE.sub(r"## \1\n\n", markdown)
    markdown = _TAGS_LINE_RE.sub(_tags_markup, markdown)

    lines = markdown.split("\n")
    h1_index = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    if h1_index is not None:
        heading = lines[h1_index]
        score = None
        match = _SCORE_IN_HEADING_RE.search(heading)
        if match:
            score = match.group(1)
            heading = heading[: match.start()]
        source_url = None
        link = _HEADING_LINK_RE.match(heading)
        if link:
            heading = f"# {link.group('title')}"
            source_url = link.group("url") or None

        # The byline is the first " \u00b7 " line after the heading, the lede the
        # first prose paragraph. Both live in the run of plain paragraphs before
        # the first block, so a single pass over that run finds them.
        byline_index = None
        lede_index = None
        for i in range(h1_index + 1, len(lines)):
            line = lines[i]
            if not line.strip():
                continue
            if line.startswith(("## ", "<", "*", ">", "-", "|", "`")):
                break  # past the intro paragraphs; nothing else qualifies
            if " \u00b7 " in line and byline_index is None:
                byline_index = i
            elif lede_index is None:
                lede_index = i

        head = [heading.rstrip()]
        if score:
            head += ["", _score_markup(score)]
        if byline_index is not None or source_url:
            byline_text = lines[byline_index] if byline_index is not None else ""
            head += [
                "",
                _byline_markup(byline_text, source_url, profile_id, issue_date),
            ]
            if byline_index is not None:
                lines[byline_index] = ""
        lines[h1_index] = "\n".join(head)
        if lede_index is not None:
            # attr_list only decorates a paragraph from its own line.
            lines[lede_index] += "\n{: .hz-lede}"

    markdown = "\n".join(lines)
    # The separator only made sense between items on a combined page. No re.M:
    # only the trailing one may go — a --- inside block content must survive.
    markdown = re.sub(r"\n---\s*$", "\n", markdown.rstrip() + "\n")
    markdown = _localize_frozen_labels(markdown)
    # The page type is declared, not inferred. The first cut hung the whole
    # article treatment — section numbering included — off `:has(.hz-byline)`,
    # which meant a page that happened to lack a byline silently rendered as
    # plain typography. `markdown="1"` needs md_in_html, which mkdocs.yml has.
    return (
        '<div class="hz-page--article" markdown="1">\n\n'
        + markdown.rstrip()
        + "\n\n</div>\n"
    )


# LABELS gained a "ru" entry only after these were written, so summaries frozen
# in data/summaries/ carry the English fallbacks. Republishing reads that frozen
# text, and the labels are structural markers rather than model output, so they
# can be translated on the way to the page. New runs already emit Russian and
# these substitutions simply find nothing.
_FROZEN_LABELS = (
    ("**Tags**", "**Теги**"),
    ("<summary>References</summary>", "<summary>Источники</summary>"),
    ("[Discussion](", "[Обсуждение]("),
)


def _localize_frozen_labels(markdown: str) -> str:
    for english, russian in _FROZEN_LABELS:
        markdown = markdown.replace(english, russian)
    return markdown


@dataclass(frozen=True)
class SummaryItemView:
    item: ContentItem
    index: int
    global_index: int
    group_count: int
    title: str
    score: float | str
    anchor_id: str


@dataclass(frozen=True)
class SummaryGroupView:
    profile_id: str
    name: str
    items: List[SummaryItemView]


@dataclass(frozen=True)
class DailySummaryView:
    groups: List[SummaryGroupView]
    item_count: int


class DailySummarizer:
    """Generates daily Markdown summaries from pre-analyzed content items."""

    def __init__(
        self,
        profile_names: Optional[Dict[str, Dict[str, str]]] = None,
        profile_order: Optional[List[str]] = None,
    ):
        self.profile_names = profile_names or {}
        self.profile_order = profile_order or []

    @staticmethod
    def _profile_id(item: ContentItem) -> str:
        if item.processing:
            return item.processing.classification.profile
        return item.profile if isinstance(item.profile, str) else "unclassified"

    def profile_name(self, profile_id: str, language: str) -> str:
        names = self.profile_names.get(profile_id, {})
        return names.get(
            language,
            names.get(
                "default",
                profile_id.replace("-", " ").replace("_", " ").title(),
            ),
        )

    def build_article_pages(
        self,
        items: List[ContentItem],
        date: str,
        language: str = "en",
    ) -> List["ArticlePage"]:
        """Render one standalone page per item, plus the issue's index page.

        The site used to publish a single page per issue with in-page anchors,
        which meant a link from a chat message landed the reader in the middle
        of a long document. One page per article gives each a URL of its own.

        The slug is the existing anchor id without its `item-` prefix, so the
        deep-link contract stays a single derivation shared with the summary's
        table of contents and the chat headline builder.
        """
        labels = LABELS.get(language, LABELS["en"])
        view = self.build_view(items, language)
        pages: List[ArticlePage] = []
        index_lines = [f"# {labels['header']} - {date}", ""]

        for group in view.groups:
            # Profile names come from config, so they are escaped like any
            # other value landing in a markdown heading.
            index_lines += [
                f"## {_escape_markdown(group.name)}",
                "",
                '<ul class="hz-list">',
            ]
            for view_item in group.items:
                slug = view_item.anchor_id.removeprefix("item-")
                body = self._format_item(
                    view_item.item,
                    labels,
                    language,
                    view_item.index,
                    heading_level=1,
                    anchor_id=view_item.anchor_id,
                    title_override=view_item.title,
                    score_override=view_item.score,
                )
                pages.append(
                    ArticlePage(
                        slug=slug,
                        title=view_item.title,
                        markdown=article_site_markup(
                            body,
                            profile_id=group.profile_id,
                            issue_date=date,
                        )
                        + _pager_markup(labels["issue"]),
                    )
                )
                index_lines.append(
                    _issue_item_markup(
                        slug, view_item.title, view_item.score, view_item.item.url
                    )
                )
            index_lines += ["</ul>", ""]

        pages.append(
            ArticlePage(
                slug="index",
                title=f"{labels['header']} - {date}",
                markdown="\n".join(index_lines).rstrip() + "\n",
            )
        )
        return pages

    def build_view(
        self,
        items: List[ContentItem],
        language: str,
    ) -> DailySummaryView:
        grouped_items: Dict[str, List[ContentItem]] = {}
        for item in items:
            grouped_items.setdefault(self._profile_id(item), []).append(item)

        ordered_groups = list(grouped_items.items())
        if self.profile_order:
            order = {
                profile_id: index
                for index, profile_id in enumerate(self.profile_order)
            }
            ordered_groups = sorted(
                ordered_groups,
                key=lambda group: order.get(group[0], len(order)),
            )

        groups = []
        global_index = 1
        for profile_id, profile_items in ordered_groups:
            view_items = []
            for index, item in enumerate(profile_items, start=1):
                artifact = (
                    item.processing.artifacts.get(language)
                    if item.processing
                    else None
                )
                analysis = item.processing.analysis if item.processing else None
                view_items.append(
                    SummaryItemView(
                        item=item,
                        index=index,
                        global_index=global_index,
                        group_count=len(profile_items),
                        title=normalize_language(
                            artifact.title if artifact else item.title, language
                        ),
                        score=(
                            analysis.score
                            if analysis and analysis.score is not None
                            else "?"
                        ),
                        anchor_id=self._item_anchor(profile_id, index),
                    )
                )
                global_index += 1
            groups.append(
                SummaryGroupView(
                    profile_id=profile_id,
                    name=normalize_language(
                        self.profile_name(profile_id, language), language
                    ),
                    items=view_items,
                )
            )
        return DailySummaryView(groups=groups, item_count=len(items))

    @staticmethod
    def _item_anchor(profile_id: str, index: int) -> str:
        safe_profile_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", profile_id).strip("-")
        return f"item-{safe_profile_id or 'unclassified'}-{index}"

    async def generate_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate daily summary in Markdown format.

        Items are rendered in score-descending order (already sorted by orchestrator).

        Args:
            items: High-scoring content items (already enriched)
            date: Date string (YYYY-MM-DD)
            total_fetched: Total number of items fetched before filtering
            language: Output language, either "en" or "zh"

        Returns:
            str: Markdown formatted summary
        """
        labels = LABELS.get(language, LABELS["en"])

        if not items:
            return self._generate_empty_summary(date, total_fetched, labels)

        header = (
            f"# {labels['header']} - {date}\n\n"
            f"> {labels['selected_items'].format(total=total_fetched, selected=len(items))}\n\n"
            "---\n\n"
        )

        toc_sections = []
        body_sections = []
        view = self.build_view(items, language)
        for group in view.groups:
            profile_name = _escape_markdown(group.name)
            if language == "zh":
                profile_name = _pangu(profile_name)
            toc_entries = [f"**{profile_name}**"]
            for view_item in group.items:
                title = _escape_markdown(view_item.title)
                if language == "zh":
                    title = _pangu(title)
                toc_entries.append(
                    f"{view_item.index}. [{title}](#{view_item.anchor_id}) "
                    f"\u2b50\ufe0f {view_item.score}/10"
                )
            toc_sections.append("\n".join(toc_entries))
            body_sections.append(f"## {profile_name}\n\n")
            body_sections.extend(
                self._format_item(
                    view_item.item,
                    labels,
                    language,
                    view_item.index,
                    heading_level=3,
                    anchor_id=view_item.anchor_id,
                    title_override=view_item.title,
                    score_override=view_item.score,
                )
                for view_item in group.items
            )

        toc = "\n\n".join(toc_sections) + "\n\n---\n\n"
        return normalize_language(header + toc + "".join(body_sections), language)

    def generate_webhook_overview(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate a compact overview for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        if not items:
            return self._generate_empty_summary(date, total_fetched, labels)

        if language == "zh":
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> 从 {total_fetched} 条内容中筛选出 {len(items)} 条重要资讯。\n\n"
                "下面会按内容逐条发送详情，你可以只看感兴趣的标题。\n\n"
            )
        else:
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> Selected {len(items)} important items from {total_fetched} fetched items.\n\n"
                "Details will be sent item by item so you can read only the topics you care about.\n\n"
            )

        sections = []
        view = self.build_view(items, language)
        for group in view.groups:
            profile_name = _escape_markdown(group.name)
            if language == "zh":
                profile_name = _pangu(profile_name)
            entries = [f"**{profile_name}**"]
            for view_item in group.items:
                title = _escape_markdown(view_item.title)
                if language == "zh":
                    title = _pangu(title)
                url = _safe_url(view_item.item.url)
                title_link = f"[{title}]({url})" if url else title
                entries.append(
                    f"{view_item.index}. {title_link} "
                    f"\u2b50\ufe0f {view_item.score}/10"
                )
            sections.append("\n".join(entries))

        return normalize_language(header + "\n\n".join(sections), language)

    def generate_webhook_item(
        self,
        item: ContentItem,
        language: str,
        index: int,
        total: int,
        *,
        title: Optional[str] = None,
        score: float | str | None = None,
    ) -> str:
        """Generate one item message for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        prefix = f"第 {index}/{total} 条\n\n" if language == "zh" else f"Item {index}/{total}\n\n"
        return normalize_language(
            prefix
            + self._format_item(
                item,
                labels,
                language,
                index,
                title_override=title,
                score_override=score,
            ).rstrip("-\n "),
            language,
        )

    def _format_item(
        self,
        item: ContentItem,
        labels: dict,
        language: str,
        index: int,
        *,
        heading_level: int = 2,
        anchor_id: Optional[str] = None,
        title_override: Optional[str] = None,
        score_override: float | str | None = None,
    ) -> str:
        """Format a single ContentItem into Markdown."""
        artifact = item.processing.artifacts.get(language) if item.processing else None
        analysis = item.processing.analysis if item.processing else None
        _title = title_override or (artifact.title if artifact else item.title)
        title = _escape_markdown(_title)
        raw_url = str(item.url)
        url = _safe_url(raw_url)
        score = (
            score_override
            if score_override is not None
            else analysis.score
            if analysis and analysis.score is not None
            else "?"
        )
        meta = item.metadata

        summary = analysis.summary if not artifact and analysis else ""
        primary_block = (
            next((block for block in artifact.blocks if block.primary), None)
            if artifact
            else None
        )

        summary = _escape_markdown(summary)
        primary_content = (
            _escape_markdown(primary_block.content) if primary_block else ""
        )

        if language == "zh":
            title = _pangu(title)
            summary = _pangu(summary)
            primary_content = _pangu(primary_content)

        # Source line with parts joined by " · ", link appended at end
        source_type = item.source_type.value
        source_parts = [_escape_markdown(source_type)]
        if meta.get("subreddit"):
            source_parts.append(_escape_markdown(f"r/{meta['subreddit']}"))
        if meta.get("feed_name"):
            source_parts.append(_escape_markdown(meta["feed_name"]))
        else:
            source_parts.append(_escape_markdown(item.author or "unknown"))
        if item.published_at:
            if language == "zh":
                source_parts.append(
                    f"{item.published_at.month}月{item.published_at.day}日 "
                    f"{item.published_at:%H:%M}"
                )
            else:
                day = item.published_at.strftime("%d").lstrip("0")
                source_parts.append(item.published_at.strftime(f"%b {day}, %H:%M"))
        source_line = " \u00b7 ".join(source_parts)  # ·

        discussion_url = meta.get("discussion_url")
        if discussion_url:
            safe_discussion_url = _safe_url(discussion_url)
            if safe_discussion_url and str(discussion_url) != raw_url:
                source_line += f' · [{labels["discussion"]}]({safe_discussion_url})'

        title_link = f"[{title}]({url})" if url else title

        lines = [
            f'<a id="{anchor_id or f"item-{index}"}"></a>',
            f"{'#' * heading_level} {title_link} \u2b50\ufe0f {score}/10",  # ⭐️
        ]
        if summary.strip():
            lines.extend(["", summary])
        if primary_content.strip():
            lines.extend(["", primary_content])
        lines.extend(["", source_line])

        if artifact:
            for block in artifact.blocks:
                if block.primary:
                    continue
                block_title = _escape_markdown(block.title)
                block_content = _escape_markdown(block.content)
                if language == "zh":
                    block_title = _pangu(block_title)
                    block_content = _pangu(block_content)
                lines.extend(["", f"**「{block_title}」** {block_content}"])

        sources = artifact.sources if artifact else []
        if sources:
            reference_items = []
            for source in sources:
                reference_title = html.escape(source.title, quote=True)
                reference_url = _safe_url(source.url)
                if reference_url:
                    reference_items.append(f'<li><a href="{reference_url}">{reference_title}</a></li>\n')
                else:
                    reference_items.append(f"<li>{reference_title}</li>\n")
            items_html = "".join(reference_items)
            lines += [
                "",
                f'<details><summary>{labels["references"]}</summary>\n<ul>\n{items_html}\n</ul>\n</details>',
            ]

        if analysis and analysis.tags:
            tags_str = ", ".join([f"`#{_escape_markdown(t)}`" for t in analysis.tags])
            lines.append("")
            lines.append(f"**{labels['tags']}**: {tags_str}")

        lines.append("")
        lines.append("---")

        return "\n".join(lines) + "\n\n"

    def _generate_empty_summary(self, date: str, total_fetched: int, labels: dict) -> str:
        """Generate summary when no high-scoring items were found."""
        return (
            f"# {labels['header']} - {date}\n\n"
            f"> {labels['empty_analyzed'].format(total=total_fetched)}\n\n"
            + labels["empty_body"]
        )
