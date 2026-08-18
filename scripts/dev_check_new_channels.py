import urllib.request
import re

for handle in ["@server-technologies", "@t3dotgg"]:
    url = f"https://www.youtube.com/{handle}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
    try:
        html_doc = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")
        m = re.search(r"channel_id=([a-zA-Z0-9_-]+)", html_doc) or re.search(r"/channel/([a-zA-Z0-9_-]+)", html_doc)
        cid = m.group(1) if m else "NOT FOUND"
        title_m = re.search(r"<title>(.*?)</title>", html_doc)
        title = title_m.group(1).replace(" - YouTube", "") if title_m else handle
        print(f"{handle} -> title: {title}, channel_id: {cid}")
        
        # Test RSS feed
        if cid != "NOT FOUND":
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
            rss_req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
            rss_doc = urllib.request.urlopen(rss_req, timeout=10).read().decode("utf-8", errors="ignore")
            entries = re.findall(r"<title>(.*?)</title>", rss_doc)
            print(f"  RSS feed works! Found {len(entries)-1} recent videos: {entries[1:4]}")
    except Exception as e:
        print(f"{handle} error: {e}")
