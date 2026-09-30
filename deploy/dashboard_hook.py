"""Native MkDocs hook: static dashboard from published pages, no API/model calls."""

import html
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.storage.dashboard import catalog, focus, newest, page_item

log = logging.getLogger("mkdocs.dashboard")
ITEMS = []
PUBLIC = {}
BY_PAGE = {}


def split_front(text):
    if text.startswith("---\n"):
        parts = text.split("\n---", 1)
        if len(parts) == 2:
            meta = yaml.safe_load(parts[0][4:]) or {}
            return meta if isinstance(meta, dict) else {}, parts[1].lstrip("\n")
    return {}, text


def on_files(files, config):
    global ITEMS, PUBLIC, BY_PAGE
    started = time.perf_counter()
    names = {}
    for file in files.documentation_pages():
        if re.fullmatch(r"digest/\d{4}-\d{2}-\d{2}-ru/index\.md", file.src_uri):
            body = file.content_string
            for match in re.finditer(r"(?m)^## ([^\n]+)\n(.*?)(?=^## |\Z)", body, re.S):
                for slug in re.findall(r'href="([\w-]+-\d+)/"', match[2]):
                    names[re.sub(r"-\d+$", "", slug)] = html.unescape(match[1])
    items = []
    failures = []
    for file in files.documentation_pages():
        if not re.fullmatch(r"digest/\d{4}-\d{2}-\d{2}-ru/[^/]+\.md", file.src_uri) or file.name == "index":
            continue
        try:
            meta, body = split_front(file.content_string)
            item = page_item(file.src_uri, body, meta, names)
            if item is None:
                raise ValueError("Unrecognized published article route")
            items.append(item)
        except (ValueError, TypeError, KeyError, yaml.YAMLError) as error:
            failures.append(file.src_uri)
            log.warning("Dashboard rejected %s: %s", file.src_uri, type(error).__name__)
    if failures:
        raise ValueError(f"Dashboard coverage incomplete: {len(failures)} published articles rejected; see build log")
    ids = [x["id"] for x in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Dashboard contains duplicate article IDs")
    ITEMS = newest(items)
    PUBLIC = catalog(ITEMS, datetime.now(timezone.utc).isoformat())
    BY_PAGE = {x["page"]: x for x in PUBLIC["items"]}
    log.info("Dashboard: %s published articles in %.3fs", len(items), time.perf_counter() - started)
    return files


def e(value):
    return html.escape(str(value), quote=True)


def icon(name):
    paths = {
        "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/>',
        "bookmark": '<path d="M6 3h12v18l-6-4-6 4z"/>',
        "close": '<path d="m6 6 12 12M18 6 6 18"/>',
    }
    return '<svg class="hd-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + paths[name] + '</svg>'


def card(item, lead=False):
    score = f'{item["score"]:.1f}<small> / 10</small>' if item["score"] is not None else '<small>без оценки</small>'
    audio = ' · <span class="hd-audio">Аудио</span>' if item["audio_ready"] else ""
    return f'''<article class="hd-story {'hd-lead' if lead else ''}" data-id="{e(item['id'])}">
<div class="hd-cover" data-cover="{e(item['cover_key'])}" data-seed="{item['cover_seed']}" aria-hidden="true"><img src="assets/dashboard/{e(item['cover_key'])}.svg" alt="" width="640" height="420"><span>ИЛЛЮСТРАЦИЯ</span></div>
<div class="hd-story-body"><div class="hd-story-top"><span>{e(item['profile_name'])}</span><span class="hd-score">{score}</span></div>
<h3><a href="{e(item['page'])}">{e(item['title'])}</a></h3><p>{e(item['teaser'])}</p>
<div class="hd-story-bottom"><span>{e(item['date'])} · ≈{item['reading_minutes']} мин{audio}</span><button class="hd-save" data-save="{e(item['id'])}" aria-label="Отложить: {e(item['title'])}" aria-pressed="false" hidden>{icon('bookmark')}</button></div></div></article>'''


def homepage():
    chosen = focus(ITEMS)
    ids = {x["id"] for x in chosen}
    feed = [x for x in ITEMS if x["id"] not in ids][:24]
    date_label = f"ПОСЛЕДНИЙ ВЫПУСК / {ITEMS[0]['date']}" if ITEMS else "ЛИЧНАЯ ЛЕНТА"
    topics = sorted({x["profile_id"]: x["profile_name"] for x in ITEMS}.items(), key=lambda x: x[1])
    filters = ''.join(f'<button data-topic="{e(p)}" aria-pressed="false">{e(n)}</button>' for p,n in topics)
    tiles = ''.join(card(x, i == 0) for i,x in enumerate(chosen))
    cards = ''.join(card(x) for x in feed)
    empty = '<h2>Пока нет опубликованных материалов</h2><p>Первый выпуск появится здесь после публикации.</p><a href="digest/">Архив выпусков →</a>'
    return f'''<div class="hd-dashboard" data-catalog="assets/dashboard/catalog.json" markdown="0">
<div class="hd-intro"><div><p class="hd-eyebrow">{date_label}</p><h1>Ваш новостной горизонт</h1><p>Важное из ваших источников. И всё, что стоит перечитать.</p></div><div class="hd-edition"><span>ОТБОР ПО ИНТЕРЕСАМ</span><b>Свежие материалы.<br>Архив без календаря.</b></div></div>
<nav class="hd-views" aria-label="Личная лента" hidden><button data-view="news" aria-pressed="true">Главная</button><button data-view="saved" aria-pressed="false">Отложенное <span data-saved-count>0</span></button><button data-view="recent" aria-pressed="false">История</button><span data-storage-note></span></nav>
<div class="hd-controls" hidden><div class="hd-search">{icon('search')}<input type="search" aria-label="Найти материал" placeholder="Заголовок, описание, тема или источник"><button data-clear-search aria-label="Очистить поиск" hidden>{icon('close')}</button></div><label>Период<select aria-label="Период публикации"><option value="all">Всё время</option><option value="7">Последние 7 дней</option><option value="30">Последние 30 дней</option></select></label><div class="hd-sort" role="group" aria-label="Порядок материалов"><button data-sort="newest" aria-pressed="true">Свежие</button><button data-sort="score" aria-pressed="false">По рейтингу</button></div></div>
<div class="hd-topics" role="group" aria-label="Темы" hidden><button data-topic="all" aria-pressed="true">Все темы</button>{filters}</div>
<div class="hd-search-help"><span>Поиск по полному тексту:</span> <a class="hd-full-search" href="search/">Поиск по архиву →</a></div>
<p class="hd-status" role="status" aria-live="polite" hidden></p><div class="hd-error" role="alert" hidden><p>Не удалось загрузить каталог. Опубликованные карточки и архив остаются доступны.</p><button data-retry>Попробовать снова</button></div>
<section class="hd-focus" {'hidden' if not chosen else ''}><div class="hd-section-heading"><h2>В фокусе</h2><span>{len(chosen)} материалов · разные темы</span></div><div class="hd-hero-grid">{tiles}</div></section>
<section class="hd-feed-section"><div class="hd-section-heading"><h2 data-feed-title>Ещё в ленте</h2><span data-result-count>{len(feed)} материалов</span></div><div class="hd-feed-layout"><div><div class="hd-feed-grid">{cards}</div><div class="hd-empty" {'hidden' if ITEMS else ''}>{'' if ITEMS else empty}</div><button class="hd-more" hidden>Показать ещё</button></div><aside class="hd-reading"><span class="hd-eyebrow">ПОД РУКОЙ</span><h2>Вернуться<br>к прочитанному</h2><div data-recent-list><p>Открытые материалы появятся здесь. Не нужно запоминать выпуск или дату.</p></div><button data-view="recent" class="hd-text-button" hidden>Вся история →</button><hr><span class="hd-eyebrow">О РЕЙТИНГЕ</span><p>Оценка интереса — не проверка истинности. Материалы с неизвестной оценкой показаны без рейтинга.</p><a href="digest/">Архив выпусков →</a></aside></div></section>
<div class="hd-footer"><p>Отложенное и история хранятся в этом браузере, без синхронизации между устройствами.</p><button data-clear-state hidden>Очистить историю</button></div></div>'''


def on_page_markdown(markdown, page, config, files):
    if page.file.src_uri == "index.md":
        page.meta["dashboard_home"] = True
        page.meta["hide"] = ["navigation", "toc"]
        return homepage()
    return markdown


def on_page_content(html_content, page, config, files):
    item = BY_PAGE.get(page.file.url)
    if item is None:
        return html_content
    snapshot = json.dumps(item, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    controls = f'''<div class="hd-article-tools" data-article-id="{e(item['id'])}"><button class="hd-save-article" data-save="{e(item['id'])}" aria-pressed="false" hidden>Отложить на потом</button><span data-storage-note></span><script type="application/json" class="hd-article-data">{snapshot}</script></div>'''
    return controls + html_content


def on_post_build(config):
    out = Path(config.site_dir) / "assets" / "dashboard" / "catalog.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(PUBLIC, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')
