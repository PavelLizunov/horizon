"""Render the configured collection scope as a public Markdown page."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import html
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from src._file_utils import _atomic_write_text
from src.models import Config


PROFILE_NAMES = {
    "tech-news": "Новости технологий",
    "tech-blog": "Технические статьи",
    "finance-news": "Финансы и рынки",
    "video": "Видео",
    "vpn-engineering": "VPN: технологии и протоколы",
    "censorship-watch": "Блокировки и доступность сети",
    "auto": "Автоматическая маршрутизация",
}

SOURCE_NAMES = {
    "github": "GitHub",
    "hackernews": "Hacker News",
    "rss": "RSS",
    "reddit": "Reddit",
    "telegram": "Telegram",
    "twitter": "X/Twitter",
    "openbb": "OpenBB",
    "ossinsight": "OSS Insight",
    "gdelt": "GDELT",
    "google_news": "Google News",
    "video": "YouTube",
    "fourpda": "4PDA",
}


def _routes(value: object) -> list[str]:
    if isinstance(value, str) and value.strip() and value != "auto":
        return [value]
    if isinstance(value, list):
        return [route for route in value if isinstance(route, str) and route.strip()]
    return ["auto"]


def _safe_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname + (f":{parsed.port}" if parsed.port else "")
    if "4pda.to" in parsed.hostname and "showtopic=" in parsed.query:
        return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, ""))
    # Query strings may contain feed keys. They are irrelevant on the public page.
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def _text(value: object, limit: int = 180) -> str:
    cleaned = " ".join(str(value or "").replace("`", "").split())
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"
    return html.escape(cleaned).replace("[", "\\[").replace("]", "\\]")


def _entry(
    rows: list[dict[str, Any]],
    source: str,
    label: object,
    config: dict[str, Any],
    *,
    url: object = None,
    fallback_profile: object = None,
) -> None:
    if not config.get("enabled", True):
        return
    rows.append(
        {
            "source": source,
            "label": _text(label),
            "url": _safe_url(url),
            "profiles": _routes(config.get("profile", fallback_profile)),
            "category": _text(config.get("category")) if config.get("category") else None,
        }
    )


def configured_sources(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return enabled, explicitly public collection descriptors only."""
    sources = config.get("sources") or {}
    rows: list[dict[str, Any]] = []

    for item in sources.get("github") or []:
        if item.get("type") == "repo_releases":
            label = f"{item.get('owner', '')}/{item.get('repo', '')} — релизы"
            url = f"https://github.com/{item.get('owner', '')}/{item.get('repo', '')}/releases"
        else:
            label = f"@{item.get('username', '')} — события пользователя"
            url = f"https://github.com/{item.get('username', '')}"
        _entry(rows, "github", label, item, url=url)

    hackernews = sources.get("hackernews") or {}
    _entry(rows, "hackernews", "лучшие истории", hackernews)

    for item in sources.get("rss") or []:
        _entry(rows, "rss", item.get("name") or "RSS-лента", item, url=item.get("url"))

    reddit = sources.get("reddit") or {}
    if reddit.get("enabled", True):
        for item in reddit.get("subreddits") or []:
            name = item.get("subreddit") or ""
            _entry(rows, "reddit", f"r/{name}", item, url=f"https://reddit.com/r/{name}")
        for item in reddit.get("users") or []:
            name = item.get("username") or ""
            _entry(rows, "reddit", f"u/{name}", item, url=f"https://reddit.com/u/{name}")

    telegram = sources.get("telegram") or {}
    if telegram.get("enabled", True):
        for item in telegram.get("channels") or []:
            channel = item.get("channel") or ""
            _entry(rows, "telegram", f"@{channel}", item, url=f"https://t.me/{channel}")

    twitter = sources.get("twitter") or {}
    if twitter and twitter.get("enabled", True):
        for username in twitter.get("users") or []:
            _entry(
                rows,
                "twitter",
                f"@{username}",
                twitter,
                url=f"https://x.com/{username}",
            )

    openbb = sources.get("openbb") or {}
    if openbb and openbb.get("enabled", True):
        for item in openbb.get("watchlists") or []:
            symbols = ", ".join(item.get("symbols") or [])
            _entry(rows, "openbb", f"{item.get('name')}: {symbols}", item)

    ossinsight = sources.get("ossinsight") or {}
    _entry(rows, "ossinsight", "трендовые репозитории", ossinsight)

    for source in ("gdelt", "google_news"):
        values = sources.get(source) or []
        for item in values if isinstance(values, list) else [values]:
            _entry(rows, source, f"поиск: {item.get('query', '')}", item)

    video = sources.get("video") or {}
    if video.get("enabled", False):
        for item in video.get("channels") or []:
            channel = item.get("channel") or ""
            _entry(
                rows,
                "video",
                item.get("name") or channel,
                item,
                url=(
                    channel
                    if str(channel).startswith(("http://", "https://"))
                    else f"https://youtube.com/{channel}"
                ),
            )

    fourpda = sources.get("fourpda") or {}
    if fourpda.get("enabled", False):
        for item in fourpda.get("topics") or []:
            tid = item.get("topic_id") or ""
            _entry(
                rows,
                "fourpda",
                item.get("name") or f"тема {tid}",
                item,
                url=f"https://4pda.to/forum/index.php?showtopic={tid}",
            )
    return rows


def _latest_run(root: Path, now: datetime) -> dict[str, Any] | None:
    if not root.exists():
        return None
    for run_dir in sorted(root.iterdir(), reverse=True):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            input_path = run_dir / manifest["input_ledger"]
            records = [
                json.loads(line)
                for line in input_path.read_text(encoding="utf-8").splitlines()
            ]
            updated = datetime.fromisoformat(
                str(manifest["updated_at"]).replace("Z", "+00:00")
            )
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            continue
        fetched = Counter(
            row.get("source_type", "unknown")
            for row in records
            if row.get("snapshot_type") == "fetched"
        )
        selected = Counter()
        for row in records:
            if row.get("snapshot_type") != "selected":
                continue
            payload = row.get("payload") or {}
            processing = payload.get("processing") or {}
            classification = processing.get("classification") or {}
            selected[classification.get("profile") or "unknown"] += 1
        return {
            "updated_at": updated.astimezone(timezone.utc),
            "age_hours": max((now - updated).total_seconds() / 3600, 0),
            "fetched": fetched,
            "selected": selected,
        }
    return None


def build_page(
    config_path: Path,
    runs_root: Path = Path("data/verification/runs"),
    *,
    now: datetime | None = None,
) -> str:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    raw = Config.model_validate(raw).model_dump(mode="json")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows = configured_sources(raw)
    processing = raw.get("processing") or {}
    digest = raw.get("digest") or {}
    profile_settings = processing.get("profile_settings") or {}
    order = list(digest.get("profile_order") or profile_settings)
    for profile in profile_settings:
        if profile not in order:
            order.append(profile)
    if any("auto" in row["profiles"] for row in rows):
        order.append("auto")

    window = int((raw.get("collection") or {}).get("time_window_hours", 24))
    run = _latest_run(runs_root, current)
    lines = [
        "# Что мы собираем",
        "",
        "Эта страница строится из **активной конфигурации Horizon** при каждой публикации. "
        "Здесь перечислены реальные включённые источники и редакционные категории, а не пример из документации.",
        "",
        "## Состояние сбора",
        "",
        f"- Окно новостей: последние **{window} ч**.",
        f"- Включено источников и поисковых лент: **{len(rows)}**.",
        f"- Активно редакционных категорий: **{len(profile_settings)}**.",
    ]
    if run:
        stamp = run["updated_at"].strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"- Последний зафиксированный запуск: **{stamp}**.")
        if run["age_hours"] > max(36, window * 1.5):
            lines += [
                "",
                '!!! warning "Сбор давно не обновлялся"',
                f"    С последнего запуска прошло {run['age_hours']:.0f} ч. "
                "Список источников актуален, но статистика запуска устарела.",
            ]
        lines += ["", "### Последний запуск", ""]
        lines.append(
            f"Собрано материалов: **{sum(run['fetched'].values())}** · "
            f"в проверочной выборке: **{sum(run['selected'].values())}**."
        )
        if run["fetched"]:
            lines += ["", "**Собрано по типам источников:** " + " · ".join(
                f"{SOURCE_NAMES.get(source, source)}: {count}"
                for source, count in sorted(run["fetched"].items())
            )]
        if run["selected"]:
            lines += ["", "**Проверочная выборка по категориям:** " + " · ".join(
                f"{PROFILE_NAMES.get(profile, profile)}: {count}"
                for profile, count in sorted(run["selected"].items())
            )]
    else:
        lines += ["", "Статистика последнего запуска пока недоступна."]

    lines += ["", "## Категории и источники"]
    for profile in order:
        profile_rows = [row for row in rows if profile in row["profiles"]]
        settings = profile_settings.get(profile) or {}
        threshold = settings.get("threshold")
        lines += ["", f"### {PROFILE_NAMES.get(profile, _text(profile))}", ""]
        if threshold is not None:
            lines.append(f"Порог отбора: **{threshold}/10**.")
            lines.append("")
        if not profile_rows:
            lines.append("Нет явно назначенных источников.")
            continue
        for row in profile_rows:
            label = f"[{row['label']}]({row['url']})" if row["url"] else row["label"]
            suffix = f" · метка `{row['category']}`" if row["category"] else ""
            if len(row["profiles"]) > 1:
                suffix += " · автовыбор между несколькими категориями"
            lines.append(
                f"- **{SOURCE_NAMES.get(row['source'], row['source'])}:** {label}{suffix}"
            )

    groups = digest.get("category_groups") or {}
    if groups:
        lines += ["", "## Рубрики VPN-радара", ""]
        for group in groups.values():
            name = _text(group.get("name") or "Без названия")
            categories = ", ".join(f"`{_text(value)}`" for value in group.get("categories") or [])
            limit = group.get("limit")
            unit = "материала" if limit == 1 else "материалов"
            lines.append(f"- **{name}** — до {limit} {unit}: {categories}.")

    lines += [
        "",
        "## Что означает «собираем»",
        "",
        "Материал из включённого источника сначала попадает в сбор, затем проходит тематическую "
        "классификацию, оценку и удаление дублей. Поэтому источник может быть активен, но в конкретном "
        "выпуске не дать ни одной статьи. Проверочная выборка — это ограниченная часть выпуска для "
        "контроля источников, а не число всех опубликованных статей.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("data/config.json"))
    parser.add_argument("--runs-root", type=Path, default=Path("data/verification/runs"))
    parser.add_argument("--write-site", type=Path, required=True)
    args = parser.parse_args()
    _atomic_write_text(args.write_site, build_page(args.config, args.runs_root))
    print(f"Wrote collection page: {args.write_site}")


if __name__ == "__main__":
    main()
