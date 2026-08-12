# telegram-reader

> Are you too fucking lazy to read your own Telegram messages and want an AI agent to read them for you? **This tool is for you!**

Fetches recent messages from **any of your chats** (groups, channels, private) with your own account, saves them as JSON + Markdown, and lets Claude (or any AI) read and analyze them.

🔒 **Never posts anything.** It only reads — no code path can send, edit, or delete a message.

## Quick start

1. **Install**
   ```sh
   pip install -r requirements.txt
   ```

2. **Get credentials** (free, ~2 min): go to [my.telegram.org](https://my.telegram.org) → *API development tools* → create an app → copy **api_id** + **api_hash**.

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

That's it. Each fetch writes two files into `data/`:

- `<chat>__<timestamp>.json` — structured, best for AI analysis
- `<chat>__<timestamp>.md` — human-readable

## Ask an AI about them

Point Claude at `data/` and ask anything — *"Summarize what happened this week"*, *"What topics keep coming up?"*, *"Find every mention of X."*

## Project structure

```
reader.py              # the tool (read-only)
config.example.json    # config template
requirements.txt       # telethon
data/                  # fetched messages (git-ignored)
```

## Notes

- **Credentials:** `config.json` (api_hash) and `session.session` (login token) are git-ignored — never share or commit them.
- **Privacy:** fetched messages stay on your machine; nothing is uploaded anywhere.
- **Python:** built on conda base — if `python` isn't your base env, use `/Users/Radin/miniconda3/bin/python`.

## License

[MIT](LICENSE) © 2026 Radin Shahdaei
