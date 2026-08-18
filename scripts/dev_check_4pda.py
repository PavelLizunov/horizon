import urllib.request
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone

url = "https://4pda.to/forum/index.php?showtopic=1110469&view=getlastpost"
req = urllib.request.Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
)

with urllib.request.urlopen(req, timeout=15) as resp:
    final_url = resp.geturl()
    content = resp.read()
    charset = resp.headers.get_content_charset() or "windows-1251"
    html_text = content.decode(charset, errors="replace")

print("Final URL:", final_url)
soup = BeautifulSoup(html_text, "html.parser")

# On 4pda, each post table or div:
# Usually <table class="ipbtable" ...> or <div data-post="..."> or <div class="post_container">
# Let's find all post containers
posts_data = []

# Method 1: find elements with data-post or class post_container / post_body
# Let's inspect elements containing post id
for post_div in soup.find_all("div", attrs={"data-post": True}):
    post_id = post_div.get("data-post")
    author_elem = post_div.find("span", class_="normalname") or post_div.find("a", href=re.compile(r"showuser=\d+"))
    author = author_elem.get_text(strip=True) if author_elem else "unknown"
    
    # Date
    date_elem = post_div.find("span", class_="postdetails") or post_div.find("span", class_="date")
    date_str = date_elem.get_text(strip=True) if date_elem else ""
    
    body_elem = post_div.find("div", class_="post_body") or post_div.find("div", class_="postcolor")
    body = body_elem.get_text(separator="\n", strip=True) if body_elem else ""
    
    posts_data.append({
        "id": post_id,
        "author": author,
        "date": date_str,
        "body": body,
        "url": f"https://4pda.to/forum/index.php?showtopic=1110469&view=findpost&p={post_id}" if post_id else final_url
    })

print(f"Parsed {len(posts_data)} posts via Method 1")

if not posts_data:
    # Method 2: table-based layout
    # 4pda IPB tables: <table ... id="post..."><div class="postcolor" id="post-...">
    for body_elem in soup.find_all("div", class_=lambda c: c and "postcolor" in c):
        post_id = body_elem.get("id", "").replace("post-", "")
        # Find author / date in parent table
        table = body_elem.find_parent("table")
        author = "unknown"
        date_str = ""
        if table:
            aname = table.find("span", class_="normalname") or table.find("a", href=re.compile(r"showuser=\d+"))
            if aname:
                author = aname.get_text(strip=True)
            # Find date: typically in <td class="row2" align="left" ...> or similar
            for td in table.find_all("td"):
                t = td.get_text(strip=True)
                if re.search(r"\d{2}\.\d{2}\.\d{2,4}|\bвчера\b|\bсегодня\b", t, re.IGNORECASE):
                    date_str = t
                    break
        
        # Remove quotes if needed or keep
        body = body_elem.get_text(separator="\n", strip=True)
        posts_data.append({
            "id": post_id,
            "author": author,
            "date": date_str,
            "body": body,
            "url": f"https://4pda.to/forum/index.php?showtopic=1110469&view=findpost&p={post_id}" if post_id else final_url
        })
    print(f"Parsed {len(posts_data)} posts via Method 2")

for i, p in enumerate(posts_data[-5:], 1):
    print(f"\n--- Post {i} (id={p['id']}, author={p['author']}, date={p['date']}) ---")
    print(f"URL: {p['url']}")
    print(p['body'][:400])
