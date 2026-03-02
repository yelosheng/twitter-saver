<div align="center">
  <img src="telegram_avatar.png" alt="Twitter Saver" width="120">
</div>

# Twitter/X Content Saver

A self-hosted tweet saver for your NAS, home server, or Raspberry Pi. Archive tweets and media to local storage with one click — no Twitter API key required.

![Python](https://img.shields.io/badge/Python-3.7%2B-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![No API Key](https://img.shields.io/badge/Twitter%20API-Not%20Required-brightgreen)

[中文文档](README.zh-CN.md)

---

## ✨ Features

- Self-hosted — runs on any Linux box, NAS, or Raspberry Pi
- No Twitter API key required — uses Playwright browser automation
- Archives single tweets (thread scraping not yet supported)
- Automatically downloads images and videos
- Saves content in multiple formats: plain text, Markdown, Reader-mode HTML
- Saves complete metadata (author, timestamp, etc.) as JSON
- Built-in task queue with automatic retry on failure (exponential backoff)
- Web UI with real-time log streaming, task monitoring, and content browsing
- Saved tweets page supports infinite scroll and pagination (toggle per preference)
- Each archived tweet gets a unique public share link
- Change password via the in-app user menu
- Optional: Telegram bot — save tweets by sending links to your private bot
- Optional: AI-powered tag generation via Gemini API
- Optional: video thumbnails via FFmpeg

---

## 🚀 Quick Start

**Prerequisites:** Python 3.7+. FFmpeg is optional (for video thumbnails).

```bash
# 1. Clone the repository
git clone https://github.com/yelosheng/twitter-saver.git
cd twitter-saver

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install Playwright browser (required)
python -m playwright install chromium

# 4. Copy and edit the config file
cp config.ini.example config.ini
```

### Web UI

```bash
python run_web.py
```

Open `http://localhost:6201` in your browser. Default login: `admin` / `admin`.

> **Change the default password immediately after first login:** click the user menu (top-right) → **Change Password**.

---

## 🖱️ Browser Extension (Tampermonkey) — Best for Desktop

The most convenient way to save tweets on a desktop browser. A Tampermonkey userscript injects a **save button** directly below each tweet on Twitter/X — one click archives the tweet and all its media without leaving the page or copying any URL.

![Save button on tweet page](X_page_tweet.png)

**Install:**
1. Install the [Tampermonkey](https://www.tampermonkey.net/) browser extension (Chrome, Firefox, Edge, or Safari)
2. Start the web UI: `python run_web.py`
3. Visit `http://localhost:6201/help` and click the install link — Tampermonkey will open a confirmation dialog
4. Click **Install** — the save button now appears on every tweet automatically

**Configure the backend URL** (required the first time, or when your server address changes):
- Click the Tampermonkey icon in your browser toolbar
- Find the **Twitter/X Archiver Save Button** script and click the settings icon
- Click **⚙️ 设置后端地址**, then enter your server address

If the server runs on the same machine as your browser, the default `http://localhost:6201` works out of the box. For a home server or NAS, use its local IP, e.g. `http://192.168.1.100:6201`.

The script file is at `tampermonkey/twitter-saver.user.js`.

---

## 🤖 Telegram Bot — Best for Mobile

The most convenient way to save tweets on a phone or tablet. Share any tweet directly to your private Telegram bot using the native Twitter/X share sheet — no URL copying, no app switching.

<img src="telegram_bot.png" alt="Telegram bot saving a tweet" width="50%">

**Setup:**
1. Open [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, follow the prompts, and copy the bot token
2. In the web UI, go to `/telegram`, paste the token, and click **Save & Start Bot**
3. Open your new bot in Telegram and send `/start` — the first person to do this becomes the permanent owner; only the owner can trigger saves
4. The bot is now ready — send or forward any `twitter.com` / `x.com` link to it and it will reply with a task ID and start saving immediately

**On mobile (the main use case):**
1. Open a tweet in the Twitter/X app
2. Tap the **Share** icon → **Share via...** → select your Telegram bot from the contact list
3. The bot receives the link and queues the download — you get a confirmation reply

**Bot commands:**
- Any message containing a Twitter/X URL → queued for archiving
- `/status` — shows current queue size

---

## ⚙️ Configuration

Copy `config.ini.example` to `config.ini` and edit as needed.

| Option | Description | Default |
|---|---|---|
| `[storage] base_path` | Directory where tweets are saved | `./saved_tweets` |
| `[storage] create_date_folders` | Create date-based subfolders | `true` |
| `[download] max_retries` | Max retry attempts on download failure | `3` |
| `[download] timeout_seconds` | Request timeout in seconds | `30` |
| `[scraper] use_playwright` | Use Playwright browser automation (recommended) | `true` |
| `[scraper] headless` | Run browser in headless mode | `true` |
| `[scraper] debug_mode` | Save screenshots on errors | `false` |
| `[ai] gemini_api_key` | Gemini API key (optional, for AI tags) | unset |
| `[telegram] bot_token` | Telegram bot token (optional, for Telegram integration) | unset |

**Environment variable overrides:**

| Variable | Description |
|---|---|
| `SAVE_PATH` | Override save path |
| `USE_PLAYWRIGHT` | Override Playwright toggle |
| `PLAYWRIGHT_HEADLESS` | Override headless mode |
| `PLAYWRIGHT_DEBUG` | Set to `true` to enable debug screenshots |
| `SSL_CERT_PATH` / `SSL_KEY_PATH` | Enable HTTPS |

---

## 📖 Usage

### Web Interface

Visit `http://localhost:6201` after starting.

| Route | Purpose |
|---|---|
| `/` | Submit a Twitter URL to start archiving |
| `/tasks` | View task queue status |
| `/saved` | Browse and search archived tweets |
| `/tags` | Manage AI-generated tags |
| `/retries` | View failed tasks and retry manually |
| `/view/<slug>` | View archived content via share link |
| `/debug` | System status and stuck task reset |
| `/telegram` | Telegram bot configuration |
| `/help` | Tampermonkey script installation guide |

### CLI

```bash
# Archive a single tweet
python main.py https://x.com/username/status/1234567890

# Skip media downloads
python main.py https://x.com/username/status/1234567890 --no-media

# Specify output directory
python main.py https://x.com/username/status/1234567890 --output /path/to/save

# Show verbose output
python main.py https://x.com/username/status/1234567890 --verbose
```

**Supported URL formats:**
```
https://twitter.com/username/status/1234567890
https://x.com/username/status/1234567890
https://mobile.twitter.com/username/status/1234567890
https://m.twitter.com/username/status/1234567890
```

---

## 📁 Output Structure

```
saved_tweets/
└── 2024-01-15_1234567890123456789/
    ├── content.txt        # Plain text
    ├── content.html       # Reader-mode HTML
    ├── content.md         # Markdown
    ├── metadata.json      # Full metadata (author, timestamp, etc.)
    ├── avatar.jpg         # Author avatar
    ├── images/
    ├── videos/
    └── thumbnails/        # Video thumbnails (requires FFmpeg)
```

---

## 🏷️ AI Tag Generation (Optional)

Automatically generates semantic tags after each successful archive to aid categorization and search. Priority order:

1. **Gemini API** — set `gemini_api_key` in `config.ini` (recommended; generous free tier).
2. **Rule-based** — no API key required; uses built-in keyword rules for basic tagging.

Manage tags on the `/tags` page, or trigger generation for individual items on the `/saved` page.

---

## 🔧 Troubleshooting

**Tweet not found** — The tweet may have been deleted or made private. Verify the URL is correct and accessible in a regular browser.

**Playwright browser not installed** — Run `python -m playwright install chromium`.

**Network issues** — Check your connection and firewall. If Twitter/X is blocked in your region, configure a proxy before using this tool.

**File permission errors** — Ensure write permission on the `base_path` directory and that sufficient disk space is available.

**Tasks stuck in processing** — Visit `/debug` in the web UI and use the "Reset Stuck Tasks" function.

**Enable debug mode** — Set `debug_mode = true` in `config.ini` or `PLAYWRIGHT_DEBUG=true`. Error screenshots will be saved in the project root.

---

## ⚠️ Disclaimer

- **For personal archival use only.** This tool is intended for saving publicly available content for offline reading and personal research.
- **Comply with Twitter/X Terms of Service.** Users are solely responsible for their usage and its legal compliance. See [Twitter/X ToS](https://twitter.com/en/tos).
- **No commercial use or mass scraping.** Do not use this tool for commercial purposes, bulk data collection, ML training, or any form of mass scraping.
- **Respect copyright.** Tweet content belongs to its original authors. Do not republish or redistribute without authorization.
- **No liability for misuse.** The author accepts no liability for any legal issues, account suspensions, or other consequences arising from misuse.

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

## 🤝 Contributing

Bug reports, feature requests, and pull requests are welcome. Please ensure existing tests pass before submitting:

```bash
python -m pytest tests/
```
