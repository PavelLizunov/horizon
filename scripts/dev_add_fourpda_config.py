import json
from pathlib import Path

config_path = Path("data/config.json")
if config_path.exists():
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sources = data.setdefault("sources", {})
    fourpda = sources.setdefault("fourpda", {})
    fourpda["enabled"] = True
    topics = fourpda.setdefault("topics", [])
    
    topic_ids = {str(t.get("topic_id")) for t in topics}
    new_topic = {
        "topic_id": 1110469,
        "name": "Суверенный Интернет – обсуждение",
        "enabled": True,
        "fetch_limit": 30,
        "category": "ru-field-report",
        "profile": "censorship-watch"
    }

    if "1110469" not in topic_ids:
        topics.append(new_topic)
        print("Added 4PDA topic 1110469")
    else:
        print("4PDA topic 1110469 already present")

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("CONFIG_UPDATED_SUCCESSFULLY")
