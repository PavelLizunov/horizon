import json
from pathlib import Path

config_path = Path("data/config.json")
if config_path.exists():
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["ai"]["analysis_concurrency"] = 2
    data["ai"]["throttle_sec"] = 0.5
    data["ai"]["enrichment_concurrency"] = 1
    data["ai"]["fallback_configs"] = [
        {
            "provider": "openai",
            "model": "deepseek-v4-flash-free",
            "base_url": "https://opencode.ai/zen/v1",
            "api_key_env": "OPENCODE_ZEN_API_KEY",
        },
        {
            "provider": "openai",
            "model": "hy3-free",
            "base_url": "https://opencode.ai/zen/v1",
            "api_key_env": "OPENCODE_ZEN_API_KEY",
        },
        {
            "provider": "openai",
            "model": "laguna-s-2.1-free",
            "base_url": "https://opencode.ai/zen/v1",
            "api_key_env": "OPENCODE_ZEN_API_KEY",
        },
    ]
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("CONFIG_UPDATED_WITH_LAGUNA")
else:
    print("NO_CONFIG")
