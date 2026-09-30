"""Offline dashboard contracts: public metadata, archive fallback and selection."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.storage.dashboard import catalog, focus, metadata, page_item, plain
from src.storage.manager import StorageManager


BODY = '''<a id="item-tech-news-1"></a>
# Реальная статья

<span class="hz-score hz-score--lead" data-tier="high">8.5<span>/10</span></span>

<p class="hz-byline"><a class="hz-source" href="https://example.com/article">example.com</a></p>

Полезное описание с **текстом**.
{: .hz-lede}

## Разбор
Длинный текст статьи.
<ul class="hz-tags"><li><a class="hz-tag" href="/search/?q=test">#test</a></li></ul>
'''


def item(number=1, profile="tech-news", day="2026-09-30", score=8.5, url=None):
    return {"id": f"{day}-ru-{profile}-{number}", "date": day, "profile_id": profile,
            "title": f"Article {profile} {number}", "score": score,
            "_dedup": url or f"unique-{profile}-{number}"}


def test_published_page_fallback_without_private_archive():
    x = page_item("digest/2026-09-30-ru/tech-news-1.md", BODY, {}, {"tech-news":"Технологии"})
    assert x["id"] == "2026-09-30-ru-tech-news-1"
    assert x["page"] == "digest/2026-09-30-ru/tech-news-1/"
    assert x["title"] == "Реальная статья"
    assert x["teaser"] == "Полезное описание с текстом."
    assert x["score"] == 8.5
    assert x["tags"] == ["test"]
    assert x["profile_name"] == "Технологии"
    assert x["audio_ready"] is False
    assert x["source_label"] == "example.com"


def test_audio_readiness_follows_attached_player():
    path = "digest/2026-09-30-ru/tech-news-1.md"
    assert not page_item(path, BODY+'<audio src="https://example.com/bad.opus"></audio>', {})["audio_ready"]
    good = BODY+'<audio class="hz-narration" src="https://example.com/ok.opus"></audio>'
    assert page_item(path, good, {})["audio_ready"]


def test_explicit_metadata_precedence_and_allowlist():
    card = metadata(title="Новый заголовок", teaser="Краткое", profile_id="agents", profile_name="Агенты", score=9)
    card.update({"reasoning":"PRIVATE", "cost":99, "verification_error":"internal"})
    x = page_item("digest/2026-09-30-ru/tech-news-1.md", BODY, {"dashboard":card})
    assert x["title"] == "Новый заголовок"
    assert x["profile_id"] == "agents"
    assert x["cover_key"] == "orbit"
    public = catalog([x], "now")
    assert "PRIVATE" not in json.dumps(public)
    assert "_dedup" not in json.dumps(public)
    assert "cost" not in json.dumps(public)


@pytest.mark.parametrize("score", [None, True, float('inf'), float('nan'), -1, 11, "bad"])
def test_unknown_invalid_scores_are_not_invented(score):
    assert metadata(title="x",teaser="",profile_id="x",profile_name="x",score=score)["score"] is None


@pytest.mark.parametrize("path", ["digest/2026-09-30-ru/../evil.md", "digest/2026-09-30-ru/index.md", "digest/2026-09-30-en/tech-news-1.md", "outside.md"])
def test_non_article_routes_ignored(path):
    assert page_item(path, BODY, {}) is None


def test_focus_deterministic_diverse_and_url_unique():
    items=[item(1,"agents",score=10,url="same"),item(2,"agents",score=9.9,url="same"),item(3,"agents",score=9.8),item(4,"agents",score=9.7),item(1,"net",score=8),item(1,"infra",score=7),item(1,"research",score=6)]
    chosen=focus(items)
    assert len(chosen)==5
    assert len({x['_dedup'] for x in chosen})==5
    assert len({x['profile_id'] for x in chosen})==4
    assert focus(list(reversed(items)))==chosen


def test_focus_widens_and_keeps_real_dates_and_missing_scores():
    items=[item(1),item(2,day="2026-09-02"),item(3,day="2026-07-01"),item(4,score=None)]
    assert len(focus(items))==4
    assert any(x['date']=="2026-07-01" for x in focus(items))
    assert focus([])==[]


def test_unknown_score_does_not_displace_scored_topic():
    candidates=[item(i,'agents',score=9-i/10) for i in range(1,6)]
    candidates.append(item(1,'unknown',score=None))
    assert all(x['score'] is not None for x in focus(candidates))


def test_metadata_plain_text_and_url_safety():
    x=metadata(title='<script>alert(1)</script>Title',teaser='**Text** [link](https://example.com) <b>bold</b>',profile_id='../../bad',profile_name='name',source_url='javascript:bad')
    assert x['title']=='Title'
    assert x['teaser']=='Text link bold'
    assert x['profile_id']=='unclassified'
    assert x['source_url']==''
    assert len(plain('long '*100))<=240


def test_front_matter_is_additive_and_json_safe(monkeypatch,tmp_path):
    import src.storage.manager as manager
    import yaml
    monkeypatch.setattr(manager,'SITE_DIGEST_DIR',tmp_path/'docs'/'digest')
    card=metadata(title='Quote: "hi"',teaser='text',profile_id='tech-news',profile_name='Технологии')
    page=SimpleNamespace(slug='tech-news-1',title='Quote: "hi"',markdown=BODY,dashboard=card)
    out=StorageManager(str(tmp_path/'data')).publish_site_pages('2026-09-30',[page],'ru')
    text=(out/'tech-news-1.md').read_text()
    parsed=yaml.safe_load(text.split('---')[1])
    assert parsed['dashboard']==card
    assert parsed['search']=={'exclude':True}
    assert text.endswith(BODY)


def test_legacy_linked_heading_keeps_identity():
    legacy='<a id="item-tech-news-1"></a>\n### [Старый материал](https://example.com/old) ⭐️ 9.0/10\n\nОписание.\n\n**Теги**: `#tag`\n'
    x=page_item('digest/2026-09-30-ru/tech-news-1.md',legacy,{})
    assert x['title']=='Старый материал'
    assert x['score']==9
    assert x['teaser']=='Описание.'


def test_new_article_metadata_uses_resolved_profile_and_excludes_reasoning():
    from src.ai.summarizer import DailySummarizer
    from test_summarizer import _make_item
    content = _make_item(1)
    content.processing.analysis.summary = 'Публичное описание'
    content.processing.analysis.reason = 'PRIVATE REASONING'
    content.profile = 'wrong-raw-profile'
    page = DailySummarizer(profile_names={'tech-news': {'ru': 'Технологии'}}).build_article_pages([content], '2026-09-30', 'ru')[0]
    assert page.dashboard['profile_id'] == 'tech-news'
    assert page.dashboard['profile_name'] == 'Технологии'
    assert page.dashboard['teaser'] == 'Публичное описание'
    assert 'PRIVATE' not in json.dumps(page.dashboard)


def test_future_metadata_version_fails_loudly():
    with pytest.raises(ValueError,match='Unsupported'):
        page_item('digest/2026-09-30-ru/tech-news-1.md',BODY,{'dashboard':{'schema_version':2}})
