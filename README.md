# telegram-reader

> Are you too fucking lazy to read your own Telegram messages and want an AI agent to read them for you? This tool is for you!

Fetches recent messages from any of your chats (groups, channels, private) with your own account, saves them as JSON + Markdown, and lets any AI read and analyze them.

**Never posts anything.** It only reads — no code path can send, edit, or delete a message.

## Quick start

1. **Install**
   ```sh
   pip install -r requirements.txt
   ```

2. **Get credentials**: go to [my.telegram.org](https://my.telegram.org) → *API development tools* → create an app → copy **api_id** + **api_hash**.

3. **Configure**
   ```sh
   cp config.example.json config.json   # paste in your api_id & api_hash
   ```

4. **Login** (one time)
   ```sh
   python reader.py login
   ```

5. **Fetch**
   ```sh
   python reader.py list                  # see your chats
   python reader.py fetch                 # pick chats interactively
   python reader.py fetch -g "My Group" --limit 200
   ```

### Forum topics

If a group has **Topics** enabled (a forum), you can list and fetch individual topics:

```sh
python reader.py topics -g "My Group"                          # list topics (id + title)
python reader.py fetch -g "My Group" -t "Housing" --limit 200  # one topic, by title
python reader.py fetch -g "My Group" -t 246845 -t "Visa"       # several topics, mixed id/title
```

Fetching *without* `-t` on a forum returns the merged recent activity across all topics.

### Date filtering

Use `--since` / `--until` (YYYY-MM-DD) to fetch only messages within a date range:

```sh
python reader.py fetch -g "My Group" -t "Visa" --since 2026-06-01 --until 2026-08-01
```

Both are optional and inclusive; combine with `--limit` to cap the result.

That's it. Each fetch writes two files into `data/`:

- `<chat>__<timestamp>.json` — structured, best for AI analysis
- `<chat>__<timestamp>.md` — human-readable

## Ask an AI about them

Point an AI agent at `data/` and ask anything.

## Search your groups

List groups matching a term (with Persian ↔ English synonyms) and their topics:

```sh
python search.py finland             # matches "finland", "فنلاند", "فینلندیا" …
python search.py آلمان               # Persian → matches German groups
```

Writes a Markdown report to `data/search__<term>__<timestamp>.md`.

## Project structure

```
reader.py              # the tool (read-only)
search.py              # search groups by regex + list topics
config.example.json    # config template
requirements.txt       # telethon
data/                  # fetched messages (git-ignored)
```
