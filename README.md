# telegram-reader

**Read-only Telegram reader.** Fetch recent messages from **any of your chats** —
groups, channels, or private conversations — using your **own account**, and
save them as JSON + Markdown for you or an AI agent (Claude) to read and
analyze.

> 🔒 **This tool never posts anything to Telegram.** It only reads. There is no
> code path that sends, edits, or deletes messages.

## Features

- **Any chat type** — groups, supergroups, channels, and private conversations
- **Your account** — reads everything you're allowed to see (Telethon / MTProto)
- **Two outputs per fetch** — structured JSON + human-readable Markdown
- **Safe by design** — read-only; config, session, and fetched data are git-ignored
- **AI-friendly** — designed to feed message dumps to Claude for analysis

## How it works

```
Your chats ──(Telethon, logged in as you)──> data/*.json + *.md ──> Claude reads & analyzes
```

Run `fetch` whenever you want, then ask Claude anything about the messages:
summarize, find topics, answer questions, track keywords, and more.

## Requirements

- Python 3.9+
- A Telegram account (free)
- API credentials from <https://my.telegram.org> (free, ~2 minutes)

## Setup

1. Install the dependency:

   ```sh
   pip install -r requirements.txt
   ```

   (This project was built with a conda base environment — activate it with
   `conda activate base`, or call the base python explicitly.)

2. Get your API credentials:
   - Go to <https://my.telegram.org>
   - Log in with your phone number
   - Open **API development tools** → create an application (any name)
   - Copy the **api_id** (number) and **api_hash** (string)

3. Create your config:

   ```sh
   cp config.example.json config.json
   ```

   Then edit `config.json` and paste in your `api_id` and `api_hash`.

## One-time login

```sh
python reader.py login
```

Enter your phone number, then the code Telegram sends you (and your 2FA
password if you have one). A `session.session` file is saved, so you only do
this once.

## Usage

```sh
python reader.py list                          # see your chats and their numbers
python reader.py fetch                         # pick chats interactively
python reader.py fetch --all --limit 200       # fetch from every chat
python reader.py fetch -g "My Group" -g 12345 --limit 100
```

Fetch any chat by name or ID — groups, channels, and private conversations all
work the same way. Each fetch saves two files into `data/`:

- `<chat>__<timestamp>.json` — structured data, best for AI analysis
- `<chat>__<timestamp>.md` — human-readable version

## Ask Claude to read them

Point Claude at the `data/` folder or a specific file and ask anything:

- "Summarize what happened in this group this week."
- "What are people discussing? Any recurring topics?"
- "Find every message mentioning X."

## Project structure

```
telegram-reader/
├── reader.py              # the fetch tool (read-only)
├── config.example.json    # config template (api_id, api_hash)
├── requirements.txt       # Python dependencies
├── data/                  # fetched messages (git-ignored)
└── session.session        # your login session (git-ignored)
```

## Security notes

- `config.json` contains your `api_hash` — never commit or share it.
- `session.session` is a login token — treat it like a password.
- Fetched messages stay on your machine; nothing is uploaded anywhere.
- `config.json`, `session.session`, and `data/` are all git-ignored.

## License

[MIT](LICENSE) © 2026 Radin Shahdaei
