"""Run two models over the same captured items and dump both outputs (dev utility).

Comparing models on different days compares the news. This replays the frozen
set from `dev_capture_items.py` through each model in turn and writes the
results side by side, so grading looks at the same inputs twice.

**This spends real money on both sides.** Keep --limit small.

    uv run python scripts/dev_capture_items.py --limit 12 --no-video
    uv run python scripts/dev_ab_models.py deepseek-v4-flash deepseek-v4-pro
"""

import argparse
import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

from src.ai.analyzer import ContentAnalyzer
from src.ai.client import create_ai_client
from src.ai.enricher import ContentEnricher
from src.ai.tokens import get_usage_snapshot, reset_usage
from src.models import ContentItem
from src.processing.profiles import ProfileRegistry
from src.storage.manager import StorageManager


async def run_model(model: str, raw_items: list[dict], config, profiles) -> dict:
    """Score and enrich a fresh copy of the items under one model."""
    reset_usage()
    # Fresh copies: analysis and enrichment mutate items in place, so reusing
    # them would let the first model's output leak into the second's input.
    items = [ContentItem.model_validate(raw) for raw in raw_items]

    ai_config = config.ai.model_copy(update={"model": model})
    client = create_ai_client(ai_config)

    analyzed = await ContentAnalyzer(client, profiles).analyze_batch(items)
    enrich = await ContentEnricher(
        client, profiles, ai_config.languages
    ).enrich_batch(analyzed)

    usage = get_usage_snapshot()
    return {
        "model": model,
        "tokens": {
            "input": usage.total_input_tokens,
            "output": usage.total_output_tokens,
        },
        "enriched_ok": enrich.succeeded_count,
        "enriched_failed": enrich.failed_count,
        "items": [item.model_dump(mode="json") for item in analyzed],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs=2, metavar="MODEL")
    parser.add_argument("--items", default="data/ab-items.json")
    parser.add_argument("--out", default="data/ab-results.json")
    args = parser.parse_args()

    load_dotenv()
    storage = StorageManager(data_dir="data")
    config = storage.load_config()
    profiles = ProfileRegistry.load(
        Path(config.processing.profiles_dir), config.processing.default_profile
    )

    raw_items = json.loads(Path(args.items).read_text(encoding="utf-8"))["items"]
    print(f"replaying {len(raw_items)} items through {len(args.models)} models\n")

    results = []
    for model in args.models:
        print(f"── {model} ──")
        results.append(await run_model(model, raw_items, config, profiles))
        last = results[-1]
        print(
            f"   tokens in/out: {last['tokens']['input']}/{last['tokens']['output']}"
            f" | enriched {last['enriched_ok']} ok, {last['enriched_failed']} failed\n"
        )

    Path(args.out).write_text(
        json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
