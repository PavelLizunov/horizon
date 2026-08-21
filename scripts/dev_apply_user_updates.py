import json
from pathlib import Path

config_path = Path("data/config.json")
if config_path.exists():
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Remove Edward Grishin YouTube channel
    channels = data.get("sources", {}).get("video", {}).get("channels", [])
    data["sources"]["video"]["channels"] = [
        ch for ch in channels
        if "UCyBZCFUN118RhbpXhEyqgZg" not in str(ch.get("channel", ""))
        and "Гришин" not in str(ch.get("name", ""))
    ]

    # 2. Update category thresholds for tech-news
    if "processing" in data and "profile_settings" in data["processing"]:
        tech_news = data["processing"]["profile_settings"].setdefault("tech-news", {})
        cat_thresh = tech_news.setdefault("category_thresholds", {})
        cat_thresh["llm"] = 4.5
        cat_thresh["ai-tools"] = 4.5
        cat_thresh["ai-workflows"] = 4.5
        cat_thresh["sdd"] = 4.5

    # 3. Add ai-tools-workflows to category_groups
    if "digest" in data and "category_groups" in data["digest"]:
        data["digest"]["category_groups"]["ai-tools-workflows"] = {
            "name": "Инструменты и подходы в использовании ИИ",
            "limit": 4,
            "categories": [
                "ai-tools",
                "ai-workflows",
                "ai-dev",
                "sdd",
                "spec-driven-development"
            ]
        }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("CONFIG_APPLIED_SUCCESSFULLY")
else:
    print("NO_CONFIG_FOUND")
