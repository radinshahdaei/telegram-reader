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

# Country groups: English name(s), demonym/adjective, Persian name(s), and a few
# key cities. Every string in a group is an alias for the others, so searching
# "هلسینکی" matches Finland-named groups too. Note: no bare 2-letter codes
# ("us", "uk", "pr", …) — their substrings would cause false expansions.
COUNTRY_GROUPS = [
    # Nordics
    ["finland", "suomi", "finnish", "فنلاند", "فینلند", "فینلاند", "فینلندیا", "فنلاندی", "هلسینکی"],
    ["sweden", "sverige", "swedish", "سوئد", "سوید", "سوئدی", "استکهلم"],
    ["norway", "norge", "norwegian", "نروژ", "نروژی", "اسلو"],
    ["denmark", "danish", "دانمارک", "دنمارک", "دانمارکی", "کپنهاگ"],
    ["iceland", "ایسلند", "ایسلندی"],
    # Western / Central Europe
    ["germany", "deutschland", "german", "آلمان", "المان", "آلمانی", "المانی", "برلین", "برلن", "مونیخ"],
    ["netherlands", "holland", "dutch", "هلند", "هلندی", "آمستردام"],
    ["belgium", "belgian", "بلژیک", "بلژیکی", "بروکسل"],
    ["luxembourg", "لوکزامبورگ"],
    ["france", "french", "فرانسه", "فرانسوی", "پاریس"],
    ["switzerland", "swiss", "سوئیس", "سوییس", "سویس", "سوئیسی", "ژنو", "زوریخ"],
    ["austria", "austrian", "اتریش", "اتریشی", "وین"],
    ["italy", "italian", "ایتالیا", "ایتالیایی", "رم", "میلان"],
    ["spain", "spanish", "اسپانیا", "اسپانیایی", "مادرید", "بارسلون"],
    ["portugal", "portuguese", "پرتغال", "پرتغالی", "لیسبون"],
    ["greece", "greek", "یونان", "یونانی", "آتن"],
    ["cyprus", "قبرس"],
    ["malta", "مالت"],
    # UK & Ireland
    ["united kingdom", "britain", "great britain", "england", "british", "english", "انگلستان", "بریتانیا", "انگلیس", "انگلیسی", "لندن"],
    ["ireland", "irish", "ایرلند", "ایرلندی", "دوبلین"],
    # Americas
    ["united states", "usa", "america", "american", "آمریکا", "امریکا", "آمریکایی", "امریکایی", "ایالات متحده"],
    ["canada", "canadian", "کانادا", "کندا", "کانادایی", "تورنتو", "مونترال", "ونکوور"],
    ["mexico", "mexican", "مکزیک", "مکزیکی"],
    ["brazil", "brazilian", "برزیل", "برزیلی"],
    ["argentina", "آرژانتین", "بوئنوس آیرس"],
    ["chile", "شیلی"],
    ["colombia", "کلمبیا"],
    ["peru", "پرو"],
    ["cuba", "کوبا"],
    # Oceania
    ["australia", "australian", "استرالیا", "استرالیایی", "سیدنی", "ملبورن"],
    ["new zealand", "نیوزیلند", "نیوزلند", "زلاند نو", "زلاندنو"],
    # Eastern Europe / Balkans
    ["russia", "russian", "روسیه", "روسی", "مسکو"],
    ["ukraine", "ukrainian", "اوکراین", "اوکراینی", "کیف"],
    ["belarus", "بلاروس", "بلاروسی"],
    ["poland", "polish", "لهستان", "لهستانی", "ورشو"],
    ["czech republic", "czechia", "czech", "چک", "جمهوری چک", "پراگ"],
    ["slovakia", "اسلواکی"],
    ["hungary", "hungarian", "مجارستان", "مجاری", "بوداپست"],
    ["romania", "romanian", "رومانی", "رومانیایی", "بخارست"],
    ["bulgaria", "bulgarian", "بلغارستان", "بلغاری", "صوفیه"],
    ["serbia", "serbian", "صربستان", "صرب", "بلگراد"],
    ["croatia", "croatian", "کرواسی", "کروات", "زاگرب"],
    ["slovenia", "اسلوونی", "اسلوونیایی"],
    ["bosnia", "بوسنی"],
    ["albania", "albanian", "آلبانی", "آلبانیایی"],
    ["north macedonia", "macedonia", "مقدونیه"],
    ["kosovo", "کوزوو"],
    ["montenegro", "مونته نگرو"],
    # Baltics
    ["estonia", "estonian", "استونی", "استونیایی", "تالین"],
    ["latvia", "لتونی", "لتونیایی", "ریگا"],
    ["lithuania", "لیتوانی", "لیتوانیایی", "ویلنیوس"],
    # Caucasus / Middle East
    ["turkey", "turkiye", "turkish", "ترکیه", "ترکی", "استانبول", "آنکارا"],
    ["azerbaijan", "آذربایجان", "باکو"],
    ["armenia", "armenian", "ارمنستان", "ارمنی", "ایروان"],
    ["georgia", "georgian", "گرجستان", "گرجی", "تفلیس"],
    ["iran", "persia", "persian", "ایران", "ایرانی", "فارسی", "تهران"],
    ["iraq", "iraqi", "عراق", "عراقی", "بغداد"],
    ["syria", "syrian", "سوریه", "سوری", "دمشق"],
    ["lebanon", "lebanese", "لبنان", "لبنانی", "بیروت"],
    ["jordan", "jordanian", "اردن", "اردنی", "امان"],
    ["palestine", "فلسطین", "فلسطینی"],
    ["israel", "اسرائیل"],
    ["saudi arabia", "saudi", "عربستان", "عربستان سعودی", "ریاض"],
    ["united arab emirates", "emirates", "امارات", "امارات متحده", "دبی", "دوبی", "ابوظبی"],
    ["qatar", "قطر", "دوحه"],
    ["kuwait", "کویت"],
    ["bahrain", "بحرین"],
    ["oman", "عمان", "مسقط"],
    # Africa
    ["egypt", "egyptian", "مصر", "مصری", "قاهره"],
    ["morocco", "مراکش", "مغرب", "رباط", "کازابلانکا"],
    ["algeria", "الجزایر"],
    ["tunisia", "تونس", "تونسی"],
    ["libya", "لیبی"],
    ["sudan", "سودان"],
    ["ethiopia", "اتیوپی"],
    ["nigeria", "نیجریه"],
    ["south africa", "آفریقای جنوبی"],
    # Asia
    ["china", "chinese", "چین", "چینی", "پکن", "شانگهای"],
    ["japan", "japanese", "ژاپن", "ژاپنی", "توکیو"],
    ["south korea", "korea", "korean", "کره", "کره جنوبی", "کره‌ای", "سئول"],
    ["taiwan", "تایوان"],
    ["hong kong", "هنگ کنگ", "هنگ‌کنگ"],
    ["singapore", "سنگاپور", "سنگاپوری"],
    ["malaysia", "malaysian", "مالزی", "مالزیایی", "کوالالامپور"],
    ["indonesia", "اندونزی"],
    ["thailand", "تایلند", "تایلندی", "بانکوک"],
    ["vietnam", "ویتنام"],
    ["philippines", "فیلیپین"],
    ["india", "indian", "هند", "هندی", "دهلی", "بمبئی"],
    ["pakistan", "pakistani", "پاکستان", "پاکستانی", "اسلام آباد"],
    ["bangladesh", "بنگلادش", "بنگلادشی"],
    ["sri lanka", "سریلانکا"],
    ["afghanistan", "afghan", "افغانستان", "افغان", "افغانستانی", "کابل"],
    ["tajikistan", "تاجیکستان"],
    ["uzbekistan", "ازبکستان"],
    ["kazakhstan", "قزاقستان", "آستانه", "الماتی"],
    ["kyrgyzstan", "قرقیزستان"],
]

# Study, migration, and day-to-day life vocabulary.
TOPIC_GROUPS = [
    # Education
    ["study", "education", "تحصیل", "تحصیلی", "دانشجویی", "دانشگاه", "university", "college"],
    ["apply", "application", "admission", "اپلای", "پذیرش"],
    ["scholarship", "fellowship", "funding", "بورس", "بورسیه", "فاند", "فول فاند"],
    ["student", "دانشجو", "دانشجوی"],
    ["master", "masters", "msc", "کارشناسی ارشد", "ارشد"],
    ["bachelor", "bachelors", "bsc", "کارشناسی", "لیسانس"],
    ["phd", "doctorate", "doctoral", "دکترا", "دکتری"],
    ["postdoc", "postdoctoral", "پست داک", "پست‌داک"],
    ["language", "زبان", "ielts", "آیلتس", "toefl", "تافل", "goethe", "گوته", "آزمون"],
    ["supervisor", "professor", "استاد", "پروفسور", "سوپروایزر"],
    ["research", "پژوهش", "تحقیق"],
    ["resume", "cv", "curriculum vitae", "رزومه", "کاور لتر", "cover letter"],
    # Visa / migration
    ["visa", "visum", "ویزا", "ویزای", "روادید"],
    ["residence", "residency", "permit", "اقامت", "اقامتی", "تمکن"],
    ["permanent residence", "اقامت دائم"],
    ["citizenship", "nationality", "passport", "تابعیت", "شهروندی", "پاسپورت"],
    ["asylum", "refugee", "پناهندگی", "پناهنده"],
    ["immigration", "migration", "migrate", "مهاجرت", "مهاجرتی", "مهاجر"],
    ["schengen", "شنگن", "شینگن"],
    ["visametric", "ویزامتریک"],
    ["tls", "tlscontact", "تی ال اس", "تی‌ال‌اس"],
    ["embassy", "consulate", "سفارت", "کنسولگری"],
    ["interview", "مصاحبه"],
    ["rejection", "rejected", "refusal", "ریجکت", "ریجکتی", "ردی"],
    ["appeal", "اعتراض"],
    # Work
    ["job", "work", "employment", "career", "کار", "شغل", "اشتغال", "کاری", "شغلی", "استخدام", "کاریابی"],
    ["salary", "income", "حقوق", "درآمد"],
    ["ausbildung", "apprenticeship", "آوسبیلدونگ", "اوسبیلدونگ", "آموزش حرفه"],
    # Life / housing / money
    ["housing", "house", "apartment", "rent", "rental", "dormitory", "dorm", "مسکن", "خانه", "اجاره", "خوابگاه"],
    ["finance", "financial", "money", "مالی", "تمکن مالی", "پول"],
    ["bank", "account", "بانک", "حساب"],
    ["health", "healthcare", "insurance", "doctor", "بیمه", "سلامت", "درمان", "درمانی", "پزشک", "دکتر"],
    ["transport", "transportation", "metro", "bus", "حمل و نقل", "مترو", "اتوبوس"],
    ["shopping", "buy", "sell", "خرید", "فروش", "خرید و فروش"],
    ["cooking", "food", "آشپزی", "غذا", "رستوران"],
    ["children", "kids", "school", "کودک", "کودکان", "مدرسه", "فرزند"],
    ["driving", "driver license", "license", "گواهینامه", "ماشین", "خودرو", "اتومبیل"],
    ["tax", "مالیات"],
    ["currency", "exchange", "ارز", "دلار", "یورو", "euro", "dollar", "تومان"],
    # Misc
    ["question", "faq", "سوال", "سوالات", "پرسش"],
    ["rules", "قوانین", "قانون", "مقررات"],
    ["suggestion", "feedback", "انتقاد", "انتقادات", "پیشنهاد", "پیشنهادات"],
    ["meetup", "gathering", "گردهمایی", "دورهمی"],
    ["announcement", "news", "اخبار", "خبر", "اطلاعیه", "اطلاع رسانی"],
    ["experience", "تجربه", "تجربیات"],
    ["counselor", "consultant", "advisor", "lawyer", "مشاور", "مشاوره", "وکیل"],
]

# Equivalent terms, grouped by concept. Every string in a group is an alias for
# the others (the first item is a readable label). Searching any alias expands
# to the whole group; aliases are normalized at load time.
SYNONYM_GROUPS = COUNTRY_GROUPS + TOPIC_GROUPS


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
