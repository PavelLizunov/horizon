"""4PDA forum topics scraper implementation."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper
from ..models import ContentItem, FourPDAConfig, FourPDATopicConfig, SourceType

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MSK_TZ = timezone(timedelta(hours=3))


def parse_4pda_date(date_str: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """Parse human Russian dates from 4PDA post headers into UTC datetimes."""
    if not date_str:
        return None
    now = now or datetime.now(MSK_TZ)
    clean = re.sub(r"\|\s*#\d+", "", date_str).strip()
    clean = clean.replace("\xa0", " ").strip()

    # "Сегодня, HH:MM"
    m = re.search(r"сегодня,\s*(\d{1,2}):(\d{2})", clean, re.IGNORECASE)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        return now.replace(hour=h, minute=mn, second=0, microsecond=0).astimezone(timezone.utc)

    # "Вчера, HH:MM"
    m = re.search(r"вчера,\s*(\d{1,2}):(\d{2})", clean, re.IGNORECASE)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=h, minute=mn, second=0, microsecond=0).astimezone(timezone.utc)

    # "DD.MM.YY, HH:MM" or "DD.MM.YYYY, HH:MM"
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4}),\s*(\d{1,2}):(\d{2})", clean)
    if m:
        d, mon, y_str, h, mn = (
            int(m.group(1)),
            int(m.group(2)),
            m.group(3),
            int(m.group(4)),
            int(m.group(5)),
        )
        y = int(y_str)
        if y < 100:
            y += 2000
        dt = datetime(y, mon, d, h, mn, 0, tzinfo=MSK_TZ)
        return dt.astimezone(timezone.utc)

    return None


class FourPDAScraper(BaseScraper):
    """Scraper for 4PDA forum topics."""

    def __init__(self, config: FourPDAConfig, http_client: httpx.AsyncClient):
        super().__init__(config.model_dump(), http_client)
        self.fourpda_config = config

    async def fetch(self, since: datetime) -> List[ContentItem]:
        if not self.config.get("enabled", True):
            return []

        tasks = []
        for topic_cfg in self.fourpda_config.topics:
            if topic_cfg.enabled:
                tasks.append(self._fetch_topic(topic_cfg, since))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        items = []
        failures = []
        for result in results:
            if isinstance(result, Exception):
                failures.append(result)
                logger.warning("Error fetching 4PDA topic: %s", result)
            elif isinstance(result, list):
                items.extend(result)

        if failures and len(failures) == len(results):
            raise RuntimeError(f"All 4PDA topics failed: {failures[0]}") from failures[0]
        return items

    async def _fetch_topic(self, cfg: FourPDATopicConfig, since: datetime) -> List[ContentItem]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
        url = f"https://4pda.to/forum/index.php?showtopic={cfg.topic_id}&view=getlastpost"
        response = await self.client.get(url, headers=headers, follow_redirects=True, timeout=30.0)
        response.raise_for_status()

        content = response.content.decode("windows-1251", errors="replace")
        soup = BeautifulSoup(content, "html.parser")

        topic_title = cfg.name or (
            soup.title.string.replace(" - 4PDA", "").strip() if soup.title else "4PDA Тема"
        )

        post_divs = soup.find_all("div", attrs={"data-post": True})

        # If the last page has few posts, optionally fetch the previous page to cover the time window
        pagination = soup.find_all("a", href=re.compile(r"st=(\d+)"))
        if len(post_divs) < 10 and pagination:
            st_vals = [
                int(m.group(1))
                for a in pagination
                if (m := re.search(r"st=(\d+)", a.get("href", "")))
            ]
            if st_vals:
                max_st = max(st_vals)
                prev_st = max_st - 20
                if prev_st >= 0:
                    prev_url = f"https://4pda.to/forum/index.php?showtopic={cfg.topic_id}&st={prev_st}"
                    try:
                        resp_prev = await self.client.get(
                            prev_url, headers=headers, follow_redirects=True, timeout=30.0
                        )
                        if resp_prev.status_code == 200:
                            prev_content = resp_prev.content.decode("windows-1251", errors="replace")
                            prev_soup = BeautifulSoup(prev_content, "html.parser")
                            prev_divs = prev_soup.find_all("div", attrs={"data-post": True})
                            post_divs = prev_divs + post_divs
                    except Exception as e:
                        logger.debug("Could not fetch previous 4PDA page: %s", e)

        items: List[ContentItem] = []
        seen_ids = set()
        for p_div in post_divs:
            pid = p_div.get("data-post")
            if not pid or pid in seen_ids:
                continue
            seen_ids.add(pid)

            date_el = p_div.find("span", class_="post_date")
            date_raw = date_el.get_text(strip=True) if date_el else ""
            pub_date = parse_4pda_date(date_raw)

            if pub_date and pub_date < since:
                continue

            nick_el = p_div.find(class_="post_nick") or p_div.find("a", href=re.compile(r"showuser=\d+"))
            author = "4pda_user"
            if nick_el:
                for icon in nick_el.find_all("i"):
                    icon.decompose()
                for dropdown in nick_el.find_all(class_="dropdown-menu"):
                    dropdown.decompose()
                a_tag = nick_el.find("a") if nick_el.name != "a" else nick_el
                if a_tag:
                    author = a_tag.get_text(strip=True).rstrip("ᵥ? ")
                else:
                    author = nick_el.get_text(strip=True).rstrip("ᵥ? ")

            body_el = p_div.find("div", class_="post_body")
            if not body_el:
                continue

            for br in body_el.find_all("br"):
                br.replace_with("\n")
            for quote in body_el.find_all("div", class_="quote_body"):
                quote.decompose()
            for qh in body_el.find_all("div", class_="quote_header"):
                qh.decompose()
            for per in body_el.find_all("div", class_="post-edit-reason"):
                per.decompose()

            text = body_el.get_text(strip=True)
            if len(text) < 15:
                continue

            # Skip pinned rules/FAQ header
            if "Правила темы" in text and "Обход блокировок" in text and len(text) > 1500:
                continue

            post_url = (
                f"https://4pda.to/forum/index.php?showtopic={cfg.topic_id}&view=findpost&p={pid}"
            )
            first_line = text.split("\n")[0].strip()
            title = f"4PDA: {first_line[:80]}..." if len(first_line) > 80 else f"4PDA: {first_line}"
            if not first_line:
                title = f"4PDA: {topic_title} — {author}"

            item = ContentItem(
                id=f"fourpda:topic:{cfg.topic_id}:{pid}",
                source_type=SourceType.FOURPDA,
                title=title,
                url=post_url,
                author=author,
                content=text,
                published_at=pub_date or datetime.now(timezone.utc),
                metadata={
                    "topic_id": str(cfg.topic_id),
                    "post_id": str(pid),
                    "topic_name": topic_title,
                    "category": cfg.category,
                    "profile": cfg.profile,
                },
            )
            items.append(item)

        return items[-cfg.fetch_limit :]
