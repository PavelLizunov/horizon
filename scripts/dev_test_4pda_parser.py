import urllib.request
import re
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

MSK_TZ = timezone(timedelta(hours=3))

def parse_4pda_date(date_str: str, now: datetime | None = None) -> datetime | None:
    if not date_str:
        return None
    now = now or datetime.now(MSK_TZ)
    # Remove post link e.g. " | #8822"
    clean = re.sub(r"\|\s*#\d+", "", date_str).strip()
    clean = clean.replace("\xa0", " ").strip()
    
    # Check "Сегодня, HH:MM"
    m = re.search(r"сегодня,\s*(\d{1,2}):(\d{2})", clean, re.IGNORECASE)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        return now.replace(hour=h, minute=mn, second=0, microsecond=0).astimezone(timezone.utc)
        
    # Check "Вчера, HH:MM"
    m = re.search(r"вчера,\s*(\d{1,2}):(\d{2})", clean, re.IGNORECASE)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=h, minute=mn, second=0, microsecond=0).astimezone(timezone.utc)
        
    # Check "DD.MM.YY, HH:MM" or "DD.MM.YYYY, HH:MM"
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4}),\s*(\d{1,2}):(\d{2})", clean)
    if m:
        d, mon, y_str, h, mn = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4)), int(m.group(5))
        y = int(y_str)
        if y < 100:
            y += 2000
        dt = datetime(y, mon, d, h, mn, 0, tzinfo=MSK_TZ)
        return dt.astimezone(timezone.utc)
        
    return None

def fetch_4pda_topic_posts(topic_id: int | str, max_posts: int = 30):
    url = f"https://4pda.to/forum/index.php?showtopic={topic_id}&view=getlastpost"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode("windows-1251", errors="replace")
        
    soup = BeautifulSoup(content, "html.parser")
    topic_title = "4PDA Тема"
    if soup.title:
        topic_title = soup.title.string.replace(" - 4PDA", "").strip()
        
    post_divs = soup.find_all("div", attrs={"data-post": True})
    
    # If the last page has fewer than 10 posts, let's also fetch the previous page
    # Look for current page 'st='
    pagination = soup.find_all("a", href=re.compile(r"st=(\d+)"))
    if len(post_divs) < 10 and pagination:
        # Get highest st
        st_vals = [int(re.search(r"st=(\d+)", a["href"]).group(1)) for a in pagination if re.search(r"st=(\d+)", a["href"])]
        if st_vals:
            max_st = max(st_vals)
            prev_st = max_st - 20
            if prev_st >= 0:
                prev_url = f"https://4pda.to/forum/index.php?showtopic={topic_id}&st={prev_st}"
                req_prev = urllib.request.Request(prev_url, headers=req.headers)
                try:
                    with urllib.request.urlopen(req_prev, timeout=15) as r_prev:
                        prev_content = r_prev.read().decode("windows-1251", errors="replace")
                        prev_soup = BeautifulSoup(prev_content, "html.parser")
                        prev_divs = prev_soup.find_all("div", attrs={"data-post": True})
                        post_divs = prev_divs + post_divs
                except Exception as e:
                    print("Error fetching prev page:", e)

    results = []
    seen_ids = set()
    for p_div in post_divs:
        pid = p_div.get("data-post")
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)
        
        # Date
        date_el = p_div.find("span", class_="post_date")
        date_raw = date_el.get_text(strip=True) if date_el else ""
        pub_date = parse_4pda_date(date_raw)
        
        # Author
        nick_el = p_div.find("span", class_="post_nick")
        author = "4pda_user"
        if nick_el:
            a_tag = nick_el.find("a")
            if a_tag:
                author = a_tag.get_text(strip=True).rstrip("ᵥ")
                
        # Body
        body_el = p_div.find("div", class_="post_body")
        if not body_el:
            continue
            
        # Clean quotes: <div class="quote_header">, <div class="quote_body">, <div class="post-edit-reason">
        # Replace <br> with \n
        for br in body_el.find_all("br"):
            br.replace_with("\n")
        
        # Strip quote boxes or format them
        for quote in body_el.find_all("div", class_="quote_body"):
            quote.decompose()
        for qh in body_el.find_all("div", class_="quote_header"):
            qh.decompose()
        for per in body_el.find_all("div", class_="post-edit-reason"):
            per.decompose()
            
        text = body_el.get_text(strip=True)
        if len(text) < 15:  # skip trivial one-word comments
            continue
            
        # Skip the pinned header post (usually huge rules/FAQ)
        if "Правила темы" in text and "Обход блокировок" in text and len(text) > 2000:
            continue
            
        post_url = f"https://4pda.to/forum/index.php?showtopic={topic_id}&view=findpost&p={pid}"
        
        results.append({
            "id": f"4pda:topic:{topic_id}:{pid}",
            "post_id": pid,
            "title": f"4PDA: {topic_title} — {author}",
            "author": author,
            "published_at": pub_date,
            "date_raw": date_raw,
            "url": post_url,
            "text": text,
        })
        
    return results

if __name__ == "__main__":
    posts = fetch_4pda_topic_posts(1110469)
    print(f"Total extracted valid user posts: {len(posts)}")
    for p in posts[-5:]:
        print(f"\n[{p['published_at']} | {p['author']}] {p['url']}")
        print(p['text'][:250])
