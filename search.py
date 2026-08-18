#!/usr/bin/env python3
"""Search your Telegram groups and list their forum topics.

The search is regex-based and language-aware:

* The query is a regular expression (case-insensitive), matched against group
  names and usernames — so ``finland|sweden`` or ``مسکن|ویزا`` both work.
* A small built-in alias map (SYNONYM_GROUPS below) lets one term match its
  Persian/English equivalents. Searching "finland" also matches "فنلاند" and
  "فینلندیا"; searching "آلمان" also matches "germany". Add entries freely.
* Persian/Arabic spelling variants are normalized before matching, so
  "فینلند" vs "فینلاند" vs "فينلند" all compare equal.

Writes a Markdown report to data/search__<query>__<timestamp>.md (override with
-o). Read-only: this script never posts, edits, or deletes anything.

Usage
-----
    python search.py finland
    python search.py "finland|sweden"
    python search.py فنلاند
    python search.py "ویزا|اقامت" -o report.md
"""

import argparse
import asyncio
import re
from datetime import datetime

from telethon import TelegramClient

from reader import DATA_DIR, SESSION_PATH, get_topics, load_config, safe_name

# Equivalent terms, grouped by concept. The first item is just a label; every
# string in a group is treated as an alias for the others. Add new groups or
# aliases freely — they are normalized at load time.
SYNONYM_GROUPS = [
    # Countries (English ↔ Persian)
    ["finland", "suomi", "فنلاند", "فینلند", "فینلاند", "فینلندیا", "فنلاندی"],
    ["sweden", "sverige", "سوئد", "سوید", "سوئدی"],
    ["germany", "deutschland", "آلمان", "المان", "آلمانی", "المانی"],
    ["norway", "norge", "نروژ"],
    ["denmark", "دانمارک", "دنمارک"],
    ["canada", "کانادا", "کندا"],
    ["austria", "اتریش"],
    ["netherlands", "holland", "هلند"],
    # Study / migration domain
    ["visa", "visum", "ویزا", "ویزای"],
    ["residence", "residency", "اقامت"],
    ["study", "تحصیل", "تحصیلی", "دانشجویی"],
    ["apply", "application", "اپلای"],
    ["job", "work", "کار", "شغل", "اشتغال"],
    ["housing", "house", "مسکن", "خانه"],
]


def normalize(text: str) -> str:
    """Lowercase and fold Persian/Arabic spelling variants so they compare equal."""
    text = text.lower()
    for a, b in (
        ("ي", "ی"),  # Arabic yeh  → Persian yeh
        ("ك", "ک"),  # Arabic kaf   → Persian kaf
        ("أ", "ا"), ("إ", "ا"), ("آ", "ا"),
        ("ة", "ه"), ("ۀ", "ه"),
        ("ؤ", "و"), ("ئ", "ی"),
    ):
        text = text.replace(a, b)
    for ch in ("‌", "‏", "‎", "؜"):  # ZWNJ / RLM / LRM / ALM
        text = text.replace(ch, "")
    return text


def compile_search(query: str) -> re.Pattern:
    """Build a regex from the query plus any synonym-group expansion.

    The query itself is kept as a regex (so "finland|sweden" works); synonyms
    are added as escaped literals. Everything is matched in normalized space.
    """
    q = normalize(query)
    parts = [q] if q.strip() else []
    for group in SYNONYM_GROUPS:
        aliases = [normalize(a) for a in group]
        if any(a in q for a in aliases):
            parts.extend(aliases)
    # dedupe, keep order
    seen, uniq = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            uniq.append(p)
    if not uniq:
        raise SystemExit("Empty search query.")
    # first part is the user's regex, the rest are literal synonyms
    body = uniq[0] + "".join("|" + re.escape(p) for p in uniq[1:])
    return re.compile("(?i)(?:" + body + ")")


async def search(client: TelegramClient, pattern: re.Pattern):
    results = []
    for d in await client.get_dialogs():
        name = normalize(d.name)
        username = normalize(getattr(d.entity, "username", "") or "")
        if not pattern.search(name + " " + username):
            continue
        topics = await get_topics(client, d.entity)
        results.append((d, topics))
    return results


def render_report(query: str, results, now: str) -> str:
    out = [
        f"# Telegram group search: `{query}`",
        "",
        f"Generated: {now}",
        f"Matched groups: {len(results)}",
        "",
    ]
    for d, topics in results:
        ent = d.entity
        username = getattr(ent, "username", None)
        is_forum = bool(getattr(ent, "forum", False))
        out.append(f"## {d.name}")
        out.append("")
        out.append(f"- id: `{d.id}`")
        if username:
            out.append(f"- username: @{username}")
        out.append(f"- unread: {d.unread_count or 0}")
        out.append(f"- type: {'forum' if is_forum else 'chat / channel'}")
        out.append("")
        if not is_forum:
            out.append("_No forum topics._")
        else:
            out.append(f"### Topics ({len(topics)})")
            out.append("")
            if not topics:
                out.append("_(none listed)_")
            for t in topics:
                flags = [f for f in ("closed", "pinned") if getattr(t, f, False)]
                flag = f" _[{', '.join(flags)}]_" if flags else ""
                out.append(f"- `{t.id}` {t.title} (unread {t.unread_count}){flag}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Search your groups (and list topics) by regex")
    p.add_argument("query", help="regex to match group names (e.g. 'finland', 'finland|sweden')")
    p.add_argument("-o", "--output", help="write report here (default data/search__<query>__<ts>.md)")
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    cfg = load_config()
    pattern = compile_search(args.query)

    client = TelegramClient(SESSION_PATH, cfg["api_id"], cfg["api_hash"])
    print("READ-ONLY mode: this tool only reads messages, it never posts.\n")
    await client.start()
    try:
        results = await search(client, pattern)
    finally:
        await client.disconnect()

    now = datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    label = safe_name(args.query) if args.query.strip() else "results"
    out_path = args.output or str(DATA_DIR / f"search__{label}__{stamp}.md")

    DATA_DIR.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render_report(args.query, results, now.isoformat(timespec="seconds")))

    print(f"Matched {len(results)} group(s):")
    for d, topics in results:
        suffix = f" ({len(topics)} topics)" if topics else ""
        print(f"  - {d.name}{suffix}")
    print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
