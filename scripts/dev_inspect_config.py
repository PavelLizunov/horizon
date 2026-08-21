import json

with open("data/config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

print("VIDEO_SOURCES:")
print(json.dumps(cfg.get("sources", {}).get("video", {}).get("channels", []), indent=2, ensure_ascii=False))
