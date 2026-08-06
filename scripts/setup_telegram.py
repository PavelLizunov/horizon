"""Interactive Telegram setup: validate a bot token and write it to .env.

Run this on the host that owns the .env — the token is read from a hidden
prompt, so it never enters shell history, a command line, an agent transcript,
or this file. Nothing prints it back.

    ssh -t <host> 'cd ~/horizon && .venv/bin/python scripts/setup_telegram.py'

The -t matters: the prompt needs a TTY.
"""

import getpass
import os
import re
import sys
from pathlib import Path

import httpx

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
URL_VAR = "TELEGRAM_WEBHOOK_URL"
TOKEN_RE = re.compile(r"^\d+:[\w-]{20,}$")


def upsert_env(path: Path, key: str, value: str) -> None:
    """Replace the key if present, append it otherwise. Never reorders."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def main() -> int:
    token = getpass.getpass("Bot token (hidden, from @BotFather): ").strip()
    if not TOKEN_RE.match(token):
        print("That does not look like a bot token (expected <digits>:<secret>).")
        return 1

    base = f"https://api.telegram.org/bot{token}"
    try:
        me = httpx.get(f"{base}/getMe", timeout=30).json()
    except Exception as e:
        print(f"Could not reach Telegram: {e}")
        return 1
    if not me.get("ok"):
        # description, not the token — safe to show.
        print(f"Telegram rejected the token: {me.get('description')}")
        return 1
    print(f"Token is valid. Bot: @{me['result'].get('username')}")

    updates = httpx.get(f"{base}/getUpdates", timeout=30).json()
    chats = {
        str(chat["id"]): chat.get("title") or chat.get("username") or chat.get("first_name")
        for entry in updates.get("result", [])
        for chat in [
            (entry.get("message") or entry.get("channel_post") or {}).get("chat", {})
        ]
        if chat.get("id")
    }
    if chats:
        print("\nchat_id candidates — put one in webhook.request_body.chat_id:")
        for chat_id, name in chats.items():
            print(f"  {chat_id}  {name}")
    else:
        print(
            "\nNo chats seen yet. Send the bot a message (or post in the channel "
            "and add the bot as an admin), then re-run to see the chat_id."
        )

    upsert_env(ENV_PATH, URL_VAR, f"{base}/sendMessage")
    print(f"\nWrote {URL_VAR} to {ENV_PATH} (chmod 600). The token is not echoed anywhere.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
