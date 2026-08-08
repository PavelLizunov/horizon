"""Unit tests for daily summary rendering."""

import asyncio
import re
from datetime import datetime, timezone

import markdown

from src.ai.summarizer import DailySummarizer, _escape_markdown, article_site_markup
from src.models import (
    ArtifactSource,
    ClassificationResult,
    ContentAnalysis,
    ContentArtifact,
    ContentBlock,
    ContentItem,
    ProcessingResult,
    SourceType,
)


def _run_async(coro):
    return asyncio.run(coro)


def _make_item(idx: int) -> ContentItem:
    item = ContentItem(
        id=f"rss:item-{idx}",
        source_type=SourceType.RSS,
        title=f"Important Item {idx}",
        url=f"https://example.com/items/{idx}",
        content="content",
        author="tester",
        published_at=datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc),
        profile="tech-news",
        processing=ProcessingResult(
            classification=ClassificationResult(
                profile="tech-news", method="source_override"
            ),
            analysis=ContentAnalysis(
                score=8.0,
                reason="test",
                summary=f"Summary for item {idx}.",
                tags=["AI", "News"],
            ),
            artifacts={
                language: ContentArtifact(
                    language=language,
                    title=f"Important Item {idx}",
                    blocks=[
                        ContentBlock(
                            id="summary",
                            title="Summary",
                            content=f"Summary for item {idx}.",
                            primary=True,
                        )
                    ],
                )
                for language in ("en", "zh")
            },
        ),
    )
    return item


def test_escape_markdown_keeps_apostrophes_renderable():
    # html.escape(quote=True) emitted &#x27;, and the markdown-special regex
    # then escaped the # *inside* it, producing a dead &\#x27;. Live in the
    # archived digest ("LLMs Can&\#x27;t Jump"), and fatal for Telegram HTML.
    escaped = _escape_markdown("LLMs Can't Jump")

    assert "&\\#" not in escaped
    assert markdown.markdown(escaped) == "<p>LLMs Can't Jump</p>"


def test_escape_markdown_still_neutralizes_html_and_markdown():
    escaped = _escape_markdown('A & B <script>alert("x")</script> *bold* [link]')

    assert "&amp;" in escaped and "&lt;script&gt;" in escaped
    assert "\\*bold\\*" in escaped and "\\[link\\]" in escaped
    assert "<script>" not in markdown.markdown(escaped)


def test_escape_markdown_leaves_pipes_alone():
    # `|` is not in Python-Markdown's ESCAPED_CHARS, so a backslash before it
    # survives into the rendered output as a literal backslash.
    assert "\\|" not in _escape_markdown("a | b")


def test_summary_toc_anchors_survive_markdown_rendering():
    """The contract that Telegram deep links depend on.

    Each item emits a bare `<a id="item-{profile}-{index}"></a>` and the table
    of contents links to it. If those ids ever stop surviving the markdown
    render, every headline link would silently land at the top of the page
    instead of the item.
    """
    items = [_make_item(idx) for idx in range(1, 4)]
    summary = _run_async(
        DailySummarizer().generate_summary(items, "2026-08-06", len(items), language="en")
    )

    targets = re.findall(r"\]\(#(item-[^)]+)\)", summary)
    assert targets, "digest produced no anchor links to check"

    rendered = markdown.markdown(summary, extensions=["toc", "md_in_html"])
    rendered_ids = set(re.findall(r'id="([^"]+)"', rendered))

    assert set(targets) <= rendered_ids, (
        f"anchors lost in rendering: {sorted(set(targets) - rendered_ids)}"
    )


def test_generate_webhook_overview_lists_items_without_full_details():
    summarizer = DailySummarizer()
    items = [_make_item(1), _make_item(2)]

    result = summarizer.generate_webhook_overview(
        items,
        date="2026-04-25",
        total_fetched=10,
        language="en",
    )

    assert "Selected 2 important items from 10 fetched items" in result
    assert "1. [Important Item 1](https://example.com/items/1)" in result
    assert "2. [Important Item 2](https://example.com/items/2)" in result
    assert "Summary for item 1." not in result


def test_generate_webhook_item_renders_single_item_detail():
    summarizer = DailySummarizer()

    result = summarizer.generate_webhook_item(
        _make_item(1),
        language="en",
        index=1,
        total=2,
    )

    assert result.startswith("Item 1/2")
    assert "## [Important Item 1](https://example.com/items/1)" in result
    assert "Summary for item 1." in result
    assert "**Tags**: `#AI`, `#News`" in result


def test_generate_webhook_item_includes_discussion_link_when_distinct():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = "https://news.ycombinator.com/item?id=1"

    result = summarizer.generate_webhook_item(
        item,
        language="en",
        index=1,
        total=1,
    )

    assert "tester · Apr 25, 08:00 · [Discussion](https://news.ycombinator.com/item?id=1)" in result


def test_generate_webhook_item_omits_discussion_link_when_same_as_item_url():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = item.url

    result = summarizer.generate_webhook_item(
        item,
        language="en",
        index=1,
        total=1,
    )

    assert "[Discussion](https://example.com/items/1)" not in result


def test_generate_webhook_item_uses_localized_discussion_label():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = "https://www.reddit.com/r/python/comments/abc123/test/"

    result = summarizer.generate_webhook_item(
        item,
        language="zh",
        index=1,
        total=1,
    )

    assert "[社区讨论](https://www.reddit.com/r/python/comments/abc123/test/)" in result


def test_generate_summary_zh_uses_localized_selection_header_and_numeric_date():
    summarizer = DailySummarizer()
    item = _make_item(1)

    result = _run_async(
        summarizer.generate_summary(
            [item],
            date="2026-04-25",
            total_fetched=10,
            language="zh",
        )
    )

    assert "> 从 10 条内容中筛选出 1 条重要资讯。" in result
    assert "rss · tester · 4月25日 08:00" in result
    assert "From 10 items" not in result
    assert "Apr 25, 08:00" not in result


def test_generate_summary_groups_items_by_profile_with_heading_hierarchy():
    news = _make_item(1)
    blog = _make_item(2)
    blog.profile = "tech-blog"
    blog.processing.classification.profile = "tech-blog"
    summarizer = DailySummarizer(
        profile_names={
            "tech-news": {"default": "Technology News", "zh": "科技新闻"},
            "tech-blog": {"default": "Technology Blog", "zh": "科技博客"},
        }
    )

    result = _run_async(
        summarizer.generate_summary(
            [news, blog],
            date="2026-04-25",
            total_fetched=2,
            language="en",
        )
    )

    assert result.count("# Digest Ninitux") == 1
    assert "## Technology News" in result
    assert "## Technology Blog" in result
    assert "### [Important Item 1]" in result
    assert "### [Important Item 2]" in result


def test_generate_summary_uses_configured_profile_order():
    finance = _make_item(1)
    finance.profile = "finance-news"
    finance.processing.classification.profile = "finance-news"
    blog = _make_item(2)
    blog.profile = "tech-blog"
    blog.processing.classification.profile = "tech-blog"
    news = _make_item(3)
    summarizer = DailySummarizer(
        profile_names={
            "tech-news": {"default": "Technology News"},
            "tech-blog": {"default": "Technology Blog"},
            "finance-news": {"default": "Financial News"},
        },
        profile_order=["tech-news", "tech-blog", "finance-news"],
    )

    result = _run_async(
        summarizer.generate_summary(
            [finance, blog, news],
            date="2026-04-25",
            total_fetched=3,
            language="en",
        )
    )

    assert result.index("## Technology News") < result.index("## Technology Blog")
    assert result.index("## Technology Blog") < result.index("## Financial News")


def test_generate_summary_renders_primary_block_before_source_without_heading():
    item = _make_item(1)
    item.processing.artifacts["en"] = ContentArtifact(
        language="en",
        title="Important Item 1",
        blocks=[
            ContentBlock(
                id="summary",
                title="Summary",
                content="Primary explanation.",
                primary=True,
            ),
            ContentBlock(
                id="background",
                title="Background",
                content="Supporting context.",
            ),
        ],
    )

    result = _run_async(
        DailySummarizer().generate_summary(
            [item],
            date="2026-04-25",
            total_fetched=1,
            language="en",
        )
    )

    assert "#### Summary" not in result
    assert result.index("Primary explanation.") < result.index(
        "rss · tester · Apr 25, 08:00"
    )
    assert result.index("rss · tester · Apr 25, 08:00") < result.index(
        "**「Background」** Supporting context."
    )


def test_generate_summary_renders_non_primary_blog_sections_after_source():
    item = _make_item(1)
    item.profile = "tech-blog"
    item.processing.classification.profile = "tech-blog"
    item.processing.artifacts["en"] = ContentArtifact(
        language="en",
        title="A technical article",
        blocks=[
            ContentBlock(
                id="background",
                title="Background",
                content="The original constraints.",
            ),
            ContentBlock(
                id="solution",
                title="Solution",
                content="The implementation and evidence.",
            ),
            ContentBlock(
                id="takeaway",
                title="Takeaway",
                content="The durable lesson.",
            ),
        ],
    )

    result = _run_async(
        DailySummarizer().generate_summary(
            [item],
            date="2026-04-25",
            total_fetched=1,
            language="en",
        )
    )

    source_index = result.index("rss · tester · Apr 25, 08:00")
    context_index = result.index("**「Background」** The original constraints.")
    solution_index = result.index("**「Solution」** The implementation and evidence.")
    takeaway_index = result.index("**「Takeaway」** The durable lesson.")
    assert source_index < context_index < solution_index < takeaway_index
    assert "#### Background" not in result


def test_generate_webhook_item_normalizes_existing_zh_artifact_to_simplified():
    item = _make_item(1)
    item.processing.artifacts["zh"] = ContentArtifact(
        language="zh",
        title="代理工作流更新",
        blocks=[
            ContentBlock(
                id="background",
                title="背景",
                content="社群關注這項更新，並分享實際用量數據。",
            )
        ],
    )

    result = DailySummarizer().generate_webhook_item(
        item,
        language="zh",
        index=1,
        total=1,
    )

    assert "代理工作流更新" in result
    assert "**「背景」** 社群关注这项更新，并分享实际用量数据。" in result
    assert "關注" not in result


def test_generate_summary_renumbers_interleaved_profiles_and_localizes_headings():
    first_news = _make_item(1)
    blog = _make_item(2)
    second_news = _make_item(3)
    blog.profile = "tech-blog"
    blog.processing.classification.profile = "tech-blog"
    summarizer = DailySummarizer(
        profile_names={
            "tech-news": {"default": "Technology News", "zh": "科技新闻"},
            "tech-blog": {"default": "Technology Blog", "zh": "科技博客"},
        }
    )

    result = _run_async(
        summarizer.generate_summary(
            [first_news, blog, second_news],
            date="2026-04-25",
            total_fetched=3,
            language="zh",
        )
    )

    assert "## 科技新闻" in result
    assert "## 科技博客" in result
    assert "1. [Important Item 1](#item-tech-news-1)" in result
    assert "2. [Important Item 3](#item-tech-news-2)" in result
    assert "1. [Important Item 2](#item-tech-blog-1)" in result
    assert result.index("2. [Important Item 3]") < result.index("1. [Important Item 2]")
    assert '<a id="item-tech-news-1"></a>' in result
    assert '<a id="item-tech-blog-1"></a>' in result


def test_generate_empty_summary_zh_uses_localized_analyzed_line():
    summarizer = DailySummarizer()

    result = _run_async(
        summarizer.generate_summary(
            [],
            date="2026-04-25",
            total_fetched=10,
            language="zh",
        )
    )

    assert "> 已分析 10 条内容，但没有达到重要性阈值的条目。" in result
    assert "Analyzed 10 items" not in result


def test_generate_summary_escapes_untrusted_text_in_all_output_contexts():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.title = '<script>alert("title")</script> [click](javascript:alert(1))'
    item.processing.analysis.summary = '<img src=x onerror="alert(1)"> **summary**'
    item.author = '<svg onload="alert(1)">'
    item.processing.analysis.tags = ['tag`](javascript:alert(1))']
    item.processing.artifacts["en"] = ContentArtifact(
        language="en",
        title=item.title,
        blocks=[
            ContentBlock(
                id="summary",
                title="Summary",
                content='<img src=x onerror="alert(1)"> **summary**',
                primary=True,
            ),
            ContentBlock(
                id="background",
                title="Background",
                content='<iframe src="data:text/html,bad"></iframe>',
            ),
            ContentBlock(
                id="community_discussion",
                title="Discussion",
                content="[bad](data:text/html,bad)",
            ),
        ],
        sources=[
            ArtifactSource(
                id="ref-1",
                title='<img src=x onerror="alert(1)">',
                url="https://example.com/ref",
            )
        ],
    )
    item.metadata.update(
        {
            "feed_name": '<b onclick="alert(1)">feed</b>',
        }
    )

    result = _run_async(summarizer.generate_summary([item], "2026-04-25", 1))

    assert "<script>" not in result
    assert "<img src=x" not in result
    assert "<iframe" not in result
    assert "<b onclick" not in result
    assert "](javascript:" not in result
    assert "](data:text/html" not in result
    assert "&lt;script&gt;" in result
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in result


def test_generate_summary_rejects_unsafe_urls_and_quote_injection():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = 'javascript:alert("discussion")'
    item.processing.artifacts["en"].sources = [
        ArtifactSource(
            id="quoted",
            title='Quoted "><script>alert(1)</script>',
            url='https://example.com/\" onmouseover=\"alert(1)',
        ),
        ArtifactSource(id="js", title="JavaScript", url="javascript:alert(1)"),
        ArtifactSource(
            id="data",
            title="Data",
            url="data:text/html,<script>alert(1)</script>",
        ),
    ]

    result = _run_async(summarizer.generate_summary([item], "2026-04-25", 1))

    assert 'href="https://example.com/%22%20onmouseover=%22alert%281%29"' in result
    assert '<li>JavaScript</li>' in result
    assert '<li>Data</li>' in result
    assert 'href="javascript:' not in result
    assert 'href="data:' not in result
    assert '<script>' not in result


def test_generate_summary_preserves_normal_http_links():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = "https://example.com/discuss?id=1#comments"
    item.processing.artifacts["en"].sources = [
        ArtifactSource(
            id="useful",
            title="Useful reference",
            url="https://docs.example.com/path?q=one&lang=en",
        )
    ]

    result = _run_async(summarizer.generate_summary([item], "2026-04-25", 1))

    assert "[Important Item 1](https://example.com/items/1)" in result
    assert "[Discussion](https://example.com/discuss?id=1#comments)" in result
    assert 'href="https://docs.example.com/path?q=one&amp;lang=en"' in result


def test_build_article_pages_one_page_per_item_plus_index():
    summarizer = DailySummarizer()
    pages = summarizer.build_article_pages(
        [_make_item(1), _make_item(2)], "2026-08-06", language="en"
    )

    slugs = [p.slug for p in pages]
    assert slugs[-1] == "index"
    assert len(pages) == 3  # two articles + the issue index


def test_build_article_pages_slug_is_the_anchor_without_its_prefix():
    # The deep-link contract: the Telegram headline builder derives the same
    # slug from the same anchor, so one page per article stays one derivation.
    summarizer = DailySummarizer()
    pages = summarizer.build_article_pages([_make_item(1)], "2026-08-06", language="en")

    anchor = DailySummarizer._item_anchor("tech-news", 1)
    assert pages[0].slug == anchor.removeprefix("item-")
    # The full anchor id survives inside the page, so nothing downstream that
    # expects item-{profile}-{index} breaks.
    assert f'id="{anchor}"' in pages[0].markdown


def test_build_article_pages_index_links_every_article():
    summarizer = DailySummarizer()
    pages = summarizer.build_article_pages(
        [_make_item(1), _make_item(2)], "2026-08-06", language="en"
    )
    index = pages[-1]

    for page in pages[:-1]:
        assert f'href="{page.slug}/"' in index.markdown


def test_build_article_pages_index_is_the_design_systems_list():
    """The issue index is the site's main working screen.

    It used to be a plain `- [title](slug.md) ⭐️ 8.0/10` list: seven identical
    stars, the only colour on a monochrome page, encoding nothing. A 4.0 and an
    8.0 were set with exactly the same weight.
    """
    summarizer = DailySummarizer()
    pages = summarizer.build_article_pages([_make_item(1)], "2026-08-06", language="en")
    index = pages[-1].markdown

    assert '<ul class="hz-list">' in index and "</ul>" in index
    assert '<li data-tier="high">' in index  # 8.0 clears the high threshold
    assert 'class="hz-item__title"' in index
    assert '<div class="hz-item__meta">example.com</div>' in index
    assert "⭐" not in index.encode("ascii", "backslashreplace").decode()


def test_build_article_pages_renders_title_as_h1():
    # MkDocs takes the page title from the first H1. The heading carries the
    # title and nothing else: the score is its own element and the source link
    # moved to the byline.
    summarizer = DailySummarizer()
    pages = summarizer.build_article_pages([_make_item(1)], "2026-08-06", language="en")

    assert "\n# Important Item 1\n" in pages[0].markdown


def test_article_head_does_not_send_the_reader_away_on_the_title():
    """The heading used to be a link to the original.

    A reader clicking what looks like the article's own name left the site
    without ever seeing the analysis the page exists for. The link belongs in
    the byline, named by its domain.
    """
    summarizer = DailySummarizer()
    pages = summarizer.build_article_pages([_make_item(1)], "2026-08-06", language="en")
    markdown = pages[0].markdown

    assert "# [Important Item 1](" not in markdown
    assert (
        '<a class="hz-source" href="https://example.com/items/1">example.com'
    ) in markdown


def test_article_head_keeps_the_score_out_of_the_permalink():
    """With the score inline the anchor came out as `#amd-taalas-8010`.

    Rescoring an article then silently changed its own address, breaking every
    external link to it.
    """
    summarizer = DailySummarizer()
    pages = summarizer.build_article_pages([_make_item(1)], "2026-08-06", language="en")

    heading = next(
        line for line in pages[0].markdown.split("\n") if line.startswith("# ")
    )
    assert "8.0" not in heading and "/10" not in heading


_ARTICLE_MD = (
    '<a id="item-tech-news-1"></a>\n'
    "# [Заголовок](https://example.com/1) ⭐️ 8.0/10\n"
    "\n"
    "Лид-абзац.\n"
    "\n"
    "rss · tester · Apr 25, 08:00\n"
    "\n"
    "**\u300cКонтекст\u300d** Текст контекста.\n"
    "\n"
    "**\u300cСуть\u300d** Текст сути.\n"
    "\n"
    "**Tags**: `#AI`\n"
    "\n"
    "---\n"
)


def test_article_site_markup_turns_block_titles_into_section_headings():
    # The complaint that started this: bold-run titles rendered
    # "visually indistinguishable from body text".
    result = article_site_markup(_ARTICLE_MD)

    assert "## Контекст\n\nТекст контекста." in result
    assert "## Суть\n\nТекст сути." in result
    assert "**\u300c" not in result


def test_article_site_markup_renders_the_score_per_the_design_contract():
    """The bare number said nothing — 9.0 and 4.0 were set identically.

    The design system encodes it twice, both monochrome: an ink tier and a
    meter whose width comes from --hz-score. Both the 4..10 normalisation and
    the 8.0/6.0 tier steps come from the published issues: 2026-08-07 ran
    4.0..8.0 in whole points, so a floor of 5 clipped a real 4.0 to nothing and
    a `high` threshold of 8.5 never fired at all.
    """
    result = article_site_markup(_ARTICLE_MD)

    assert 'class="hz-score hz-score--lead"' in result
    assert 'data-tier="high"' in result          # 8.0 reaches high
    assert "--hz-score:0.67" in result           # (8.0 - 4) / 6
    assert '<span class="hz-score__scale">/10</span>' in result
    assert "⭐" not in result.encode("ascii", "backslashreplace").decode()


def test_article_site_markup_puts_the_byline_above_the_lede():
    """The byline used to sit *under* the summary.

    That put the reader through four sentences of text before anything said
    where the text came from. It is also where the source link now lives.
    """
    result = article_site_markup(_ARTICLE_MD, profile_id="tech-news")

    byline = result.index('<p class="hz-byline">')
    assert byline < result.index("{: .hz-lede}")
    assert result.index("# Заголовок") < byline
    # The profile is a chip with an icon, not a bare internal token, and "rss"
    # — which names our plumbing, not a source — is gone.
    assert '<span class="hz-i hz-i--news" aria-hidden="true"></span>tech-news' in result
    assert "rss" not in result
    assert "tester · Apr 25, 08:00" in result


def test_article_site_markup_renders_tags_as_the_design_systems_list():
    # The pill belongs to .hz-tag alone: styling `code` for it would have
    # caught every command and path the digest quotes in prose.
    result = article_site_markup(_ARTICLE_MD)

    assert '<ul class="hz-tags">' in result
    assert '<a class="hz-tag" href="/search/?q=AI">#AI</a>' in result
    assert "`#AI`" not in result


def test_article_site_markup_strips_tool_citation_ids():
    """The analyst leaves internal call ids in its prose.

    They name tool invocations: the reader cannot follow them and the sources
    they stand for never reach the page. Frozen summaries carry the
    markdown-escaped shape, live output the raw one; both must go, and neither
    may leave a stranded space before the full stop.
    """
    frozen = (
        "# T\n\nЛид.\n\nrss · a · Apr 25\n\n"
        "Подтверждается пресс-релизами \\[tool-2-1\\]\\[tool-2-2\\]. "
        "И вторым [tool-3-1].\n"
    )
    result = article_site_markup(frozen)

    assert "tool-2-1" not in result and "tool-3-1" not in result
    assert "пресс-релизами." in result
    assert "вторым." in result


def test_article_site_markup_drops_the_trailing_separator():
    result = article_site_markup(_ARTICLE_MD)
    assert not result.rstrip().endswith("---")
    # The block content itself must survive untouched.
    assert "Текст сути." in result


def test_ru_digest_uses_russian_chrome_labels():
    # A ru digest falling back to en labels ("References", "Tags") reads as a
    # bug on the site. The header stays the brand name.
    item = _make_item(1)
    item.processing.artifacts["ru"] = ContentArtifact(
        language="ru",
        title="Важный материал 1",
        blocks=[
            ContentBlock(id="summary", title="Суть", content="Суть материала.", primary=True)
        ],
        sources=[ArtifactSource(id="s1", title="Оригинал", url="https://example.com/items/1")],
    )

    summarizer = DailySummarizer()
    result = _run_async(summarizer.generate_summary([item], "2026-04-25", 1, language="ru"))

    assert "# Digest Ninitux" in result
    assert "Источники" in result and "References" not in result
    assert "Теги" in result and "**Tags**" not in result


def test_frozen_english_labels_are_localized_on_site_pages():
    """Summaries frozen before LABELS gained "ru" carry English markers.

    They are structural labels, not model output, so republishing an archived
    issue can translate them on the way to the page rather than leaving three
    English words in an otherwise Russian article.
    """
    from src.ai.summarizer import article_site_markup

    frozen = (
        "# Title\n\n"
        "**Tags**: `#ai`\n\n"
        "<details><summary>References</summary>\n<ul></ul>\n</details>\n\n"
        "rss · a · [Discussion](https://e.com)\n"
    )
    out = article_site_markup(frozen)

    # The tags line no longer carries a label at all — it became .hz-tags.
    assert '<a class="hz-tag" href="/search/?q=ai">#ai</a>' in out
    assert "**Tags**" not in out
    assert "<summary>Источники</summary>" in out and "References" not in out
    assert "[Обсуждение](" in out and "[Discussion](" not in out
