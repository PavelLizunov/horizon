import urllib.request

url = "https://4pda.to/forum/index.php?act=rssout&t=1110469"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        content = r.read().decode("windows-1251", errors="replace")
        print("First 500 chars:")
        print(content[:500])
except Exception as e:
    print("Error:", e)
