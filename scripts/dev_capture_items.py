"""Capture a replayable set of ContentItems for the model A/B (dev utility).

Both models must score the *same* items or the comparison means nothing — a
different day is different news. This fetches once and freezes the result to
JSON; `dev_ab_models.py` then replays it through each model.

Fetching itself spends no LLM tokens. The one exception is the video source's
vision fallback, which calls the AI on videos that yield no transcript; pass
`--no-video` to remove that possibility entirely.

    uv run python scripts/dev_capture_items.py --hours 24 --limit 15
"""

import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.orchestrator import HorizonOrchestrator
from src.storage.manager import StorageManager

DEFAULT_OUT = Path("data/ab-items.json")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--limit", type=int, default=15, help="items to keep (0 = all)")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--no-video",
        action="store_true",
        help="disable the video source so no vision-fallback tokens are spent",
    )
    args = parser.parse_args()

    load_dotenv()
    storage = StorageManager(data_dir="data")
    config = storage.load_config()
    if args.no_video:
        config.sources.video.enabled = False

    orchestrator = HorizonOrchestrator(config, storage)
    since = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    items = await orchestrator.fetch_all_sources(since)
    if args.limit:
        items = items[: args.limit]

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "since": since.isoformat(),
        "items": [item.model_dump(mode="json") for item in items],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"captured {len(items)} items -> {out}")
    by_source: dict[str, int] = {}
    for item in items:
        by_source[item.source_type.value] = by_source.get(item.source_type.value, 0) + 1
    for source, count in sorted(by_source.items()):
        print(f"  {source:14} {count}")


if __name__ == "__main__":
    asyncio.run(main())
