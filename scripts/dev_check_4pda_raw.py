import urllib.request
import re
from bs4 import BeautifulSoup

url = "https://4pda.to/forum/index.php?showtopic=1110469&view=getlastpost"
req = urllib.request.Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
)

with urllib.request.urlopen(req, timeout=15) as resp:
    html_text = resp.read().decode("windows-1251", errors="replace")

soup = BeautifulSoup(html_text, "html.parser")
post_divs = soup.find_all("div", attrs={"data-post": True})
if post_divs:
    p = post_divs[-1]
    print("=== RAW HTML OF LAST POST ===")
    print(str(p)[:2000])
