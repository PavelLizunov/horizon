"""Dispatch deferred webhook notifications after verified site publication."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

from src.models import Config
from src.services.webhook import WebhookNotifier
from src.storage.manager import StorageManager


async def dispatch() -> int:
    load_dotenv()
    storage = StorageManager()
    try:
        config = storage.load_config()
    except Exception as error:  # noqa: BLE001
        print(f"Error loading config: {error}", file=sys.stderr)
        return 1

    if not config.webhook or not config.webhook.enabled:
        print("Webhook is disabled; nothing to dispatch.")
        return 0

    notifier = WebhookNotifier(config.webhook)
    pending_files = sorted(storage.data_dir.glob("pending-webhook-*.json"))
    if not pending_files:
        print("No pending webhooks to dispatch.")
        return 0

    total_dispatched = 0
    failures = 0
    for pfile in pending_files:
        try:
            messages = json.loads(pfile.read_text(encoding="utf-8"))
            print(f"Dispatching {len(messages)} message(s) from {pfile.name}...")
            file_failed = False
            for msg in messages:
                res = await notifier.notify(msg)
                if not res.sent:
                    print(
                        f"  Delivery failure: {res.status.value} (code={res.status_code})",
                        file=sys.stderr,
                    )
                    file_failed = True
                    failures += 1
                else:
                    total_dispatched += 1
            if not file_failed:
                pfile.unlink(missing_ok=True)
        except Exception as error:  # noqa: BLE001
            print(f"Error processing {pfile}: {error}", file=sys.stderr)
            failures += 1

    print(f"Webhook dispatch complete: {total_dispatched} sent, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(dispatch()))
