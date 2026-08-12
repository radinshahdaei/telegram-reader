#!/usr/bin/env python3
"""Read-only Telegram reader.

Fetches recent messages from any of your chats (groups, channels, private
conversations) and saves them to data/ as JSON and Markdown. Logs in with YOUR
account (Telethon / MTProto). This script NEVER sends, edits, or deletes any
message — it only reads.

Setup
-----
1.  pip install -r requirements.txt
2.  cp config.example.json config.json   # then fill in api_id / api_hash
    (get them free at https://my.telegram.org/apps)
3.  python reader.py login               # one-time login (phone + code + maybe 2FA)
4.  python reader.py fetch               # pick groups interactively
"""

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.custom import Message

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
DATA_DIR = BASE / "data"
SESSION_PATH = str(BASE / "session")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(
            "config.json not found.\n"
            "  cp config.example.json config.json\n"
            "  then fill in your api_id and api_hash from https://my.telegram.org/apps"
        )
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not cfg.get("api_id") or not cfg.get("api_hash"):
        sys.exit("config.json must set api_id (number) and api_hash (string).")
    return cfg


def safe_name(name: str) -> str:
    # Keep word chars from any language so Persian group names survive, plus . and -
    return re.sub(r"[^\w.-]+", "_", name).strip("_") or "chat"


def display_name(entity) -> str:
    name = (
        getattr(entity, "title", None)
        or getattr(entity, "first_name", None)
        or getattr(entity, "username", None)
        or "Unknown"
    )
    username = getattr(entity, "username", None)
    return f"{name} (@{username})" if username else str(name)


def media_type(m: Message):
    """Return a short label for attached media, or None."""
    if m.media is None:
        return None
    for attr in ("photo", "video", "voice", "audio", "sticker",
                 "video_note", "gif", "webpage", "poll", "dice", "contact"):
        if getattr(m, attr, None) is not None:
            return attr
    if m.document:
        return "document"
    return type(m.media).__name__.lower()


async def serialize(client: TelegramClient, m: Message, chat_name: str, chat_id) -> dict:
    sender = None
    if m.sender_id is not None:
        try:
            sender = display_name(await client.get_entity(m.sender_id))
        except Exception:
            sender = str(m.sender_id)
    return {
        "chat": chat_name,
        "chat_id": chat_id,
        "id": m.id,
        "date": m.date.isoformat() if m.date else None,
        "out": bool(m.out),
        "sender_id": m.sender_id,
        "sender": sender,
        "text": m.message or "",
        "media": media_type(m),
        "reply_to": getattr(m, "reply_to_msg_id", None),
        "views": m.views,
    }


def render_markdown(dialog, records: list) -> str:
    lines = [f"# {dialog.name}", ""]
    if records:
        lines.append(
            f"Fetched: {datetime.now().isoformat(timespec='seconds')} — "
            f"{len(records)} messages"
        )
        lines.append(f"Range: {records[0]['date']} → {records[-1]['date']}")
    lines.append("")
    for r in records:
        when = (r["date"] or "").replace("T", " ")[:16]
        lines.append(f"## {when} · {r['sender'] or r['sender_id']}")
        if r["media"]:
            lines.append(f"_[media: {r['media']}]_")
        if r["text"]:
            lines.append("")
            lines.append(r["text"])
        lines.append("")
    return "\n".join(lines)


def write_outputs(dialog, records: list) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = f"{safe_name(dialog.name)}__{stamp}"
    json_path = DATA_DIR / f"{base}.json"
    md_path = DATA_DIR / f"{base}.md"

    json_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(render_markdown(dialog, records), encoding="utf-8")
    print(f"  saved {len(records)} messages")
    print(f"  JSON:      {json_path}")
    print(f"  Markdown:  {md_path}")


async def fetch_dialog(client: TelegramClient, dialog, limit: int) -> None:
    print(f"\nFetching up to {limit} messages from: {dialog.name}")
    messages = await client.get_messages(dialog.entity, limit=limit)
    records = []
    for m in messages:
        if isinstance(m, Message):
            records.append(await serialize(client, m, dialog.name, dialog.id))
    records.sort(key=lambda r: r["date"] or "")
    write_outputs(dialog, records)


async def list_dialogs(client: TelegramClient) -> None:
    dialogs = await client.get_dialogs()
    print(f"{len(dialogs)} chats:")
    for i, d in enumerate(dialogs):
        print(f"  {i:3}. [{d.id}] {d.name}  (unread={d.unread_count or 0})")


def select_dialogs(dialogs, args) -> list:
    if args.all:
        return dialogs
    if args.groups:
        selected = []
        for g in args.groups:
            matches = [d for d in dialogs if d.name == g or str(d.id) == g]
            if matches:
                selected.extend(matches)
            else:
                print(f"! no chat found matching '{g}' (try `python reader.py list`)")
        return selected
    if not sys.stdin.isatty():
        sys.exit("No group selected and stdin is not a terminal. Use --all or -g 'Name'.")
    print("\nChats:")
    for i, d in enumerate(dialogs):
        print(f"  {i:3}. {d.name}")
    raw = input("\nPick numbers (comma separated) or 'all': ").strip()
    if raw.lower() == "all":
        return dialogs
    idx = [int(x) for x in re.split(r"[,\s]+", raw) if x.strip().isdigit()]
    return [dialogs[i] for i in idx if 0 <= i < len(dialogs)]


async def run(args) -> None:
    cfg = load_config()
    client = TelegramClient(SESSION_PATH, cfg["api_id"], cfg["api_hash"])
    print("READ-ONLY mode: this tool only reads messages, it never posts.\n")
    await client.start()
    me = await client.get_me()
    print(f"Logged in as: {display_name(me)}\n")

    if args.command == "login":
        print("Login OK — session saved.")
    elif args.command == "list":
        await list_dialogs(client)
    elif args.command == "fetch":
        dialogs = await client.get_dialogs()
        selected = select_dialogs(dialogs, args)
        if not selected:
            print("Nothing selected.")
        else:
            limit = args.limit or cfg.get("default_limit", 100)
            for d in selected:
                try:
                    await fetch_dialog(client, d, limit)
                except Exception as e:
                    print(f"  ! failed on {d.name}: {e}")

    await client.disconnect()
    print("\nDone.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Read-only Telegram reader")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="one-time login, saves session")
    sub.add_parser("list", help="list your chats/groups")

    fetch = sub.add_parser("fetch", help="fetch recent messages from chats")
    fetch.add_argument("-g", "--group", dest="groups", action="append",
                       help="group name or id (repeatable)")
    fetch.add_argument("--all", action="store_true", help="fetch from every chat")
    fetch.add_argument("--limit", type=int, help="recent messages per group")

    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
