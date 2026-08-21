import json
from pathlib import Path

config_path = Path("data/config.json")
if config_path.exists():
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    video = data.setdefault("sources", {}).setdefault("video", {})
    channels = video.setdefault("channels", [])

    existing_handles = {str(c.get("channel", "")).lower() for c in channels}
    
    new_channels = [
        {
            "name": "Серверные Технологии",
            "channel": "@server-technologies",
            "max_videos": 3,
            "profile": "video"
        },
        {
            "name": "Theo - t3.gg",
            "channel": "@t3dotgg",
            "max_videos": 3,
            "profile": "video"
        }
    ]

    for nc in new_channels:
        if nc["channel"].lower() not in existing_handles:
            channels.append(nc)
            print(f"Added channel: {nc['name']} ({nc['channel']})")
        else:
            print(f"Channel already exists: {nc['channel']}")

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("CONFIG_UPDATED_SUCCESSFULLY")
