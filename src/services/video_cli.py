"""CLI entry point for the video sidecar.

Runs the YouTube extraction ladder on its own, outside the digest pipeline, and
writes the resulting items to the inbox file that `sources.video.mode:
"sidecar"` reads. Splitting the two means yt-dlp breakage, expired cookies, a
missing `node`, or a slow whisper pass cost the video section of one digest
instead of delaying or destabilising the whole run — and it lets the heavy job
run on an Apple Silicon box while the digest runs anywhere.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich.console import Console

from .._cli import add_data_dir_arguments, add_log_level_argument
from ..logging_config import configure_logging
from ..models import Config
from ..scrapers.video import VideoScraper, write_inbox
from ..storage.manager import ConfigError, StorageManager

console = Console(stderr=True)


async def _collect(config: Config, hours: int, inbox: Path) -> int:
    """Fetch every enabled channel and write the inbox. Returns item count."""
    # Force inline: this process *is* the sidecar, so honouring a "sidecar"
    # mode here would make it read the file it is supposed to produce.
    video_cfg = config.sources.video.model_copy(update={"mode": "inline"})
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    async with httpx.AsyncClient(timeout=60.0) as client:
        scraper = VideoScraper(video_cfg, client, config.ai)
        items = await scraper.fetch(since)

    write_inbox(inbox, items, scraper.last_run_stats)
    stats = scraper.last_run_stats
    console.print(f"Wrote {len(items)} item(s) to [cyan]{inbox}[/cyan]")
    console.print(f"Breakdown: {stats.summary()}")
    if stats.graded:
        console.print(f"Transcript rate: {stats.transcript_rate:.0%}")
    return len(items)


def main() -> None:
    """Entry point for the `horizon-video` command."""
    configure_logging(console)

    parser = argparse.ArgumentParser(
        description="Horizon video sidecar - collect YouTube items into an inbox file"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Collect videos published in the last N hours (default: 24)",
    )
    parser.add_argument(
        "-o", "--inbox",
        default=None,
        metavar="PATH",
        help="Inbox file to write (default: sources.video.inbox_file from config)",
    )
    add_data_dir_arguments(parser)
    # This job is meant to be watched, so default to a talkative level: the
    # preflight and run-summary lines are the whole point of running it.
    add_log_level_argument(parser, default="INFO")
    args = parser.parse_args()
    configure_logging(console, level=args.log_level)

    load_dotenv()

    try:
        storage = StorageManager(data_dir=args.data_dir, config_path=args.config)
        config = storage.load_config()
    except (ConfigError, FileNotFoundError) as e:
        console.print(f"[bold red]Configuration error:[/bold red] {e}")
        sys.exit(1)

    video_cfg = config.sources.video
    if not video_cfg.channels:
        console.print("[yellow]No channels configured under sources.video[/yellow]")
        sys.exit(1)

    inbox = Path(args.inbox or video_cfg.inbox_file).expanduser()
    try:
        asyncio.run(_collect(config, args.hours, inbox))
    except Exception as e:
        # The scraper swallows per-channel failures itself; reaching here means
        # something structural broke, and the exit code should say so.
        console.print(f"[bold red]Video sidecar failed:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
