import urllib.request

urls = [
    "https://4pda.to/forum/index.php?act=rssout&t=1110469",
    "https://4pda.to/forum/index.php?act=rssout&id=1110469",
    "https://4pda.to/forum/index.php?act=rssout&f=1110469",
    "https://4pda.to/forum/rss.php",
    "https://4pda.to/rss/",
]

for u in urls:
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            print(f"{u} -> {r.status}, content-type: {r.headers.get('content-type')}, len: {len(r.read(200))}")
    except Exception as e:
        print(f"{u} -> Error: {e}")
