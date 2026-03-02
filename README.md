# Twitter/X Content Archiver

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
- Each archived tweet gets a unique public share link
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

> **Change the default password immediately after first login:**
> ```bash
> python tools/change_password.py
> ```

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

1. **Gemini API** — set `gemini_api_key` in `config.ini` (recommended; generous free tier). Prompt template is in `prompts.ini`.
2. **Rule-based** — no API key required; uses built-in keyword rules for basic tagging.

Manage tags on the `/tags` page, or trigger generation for individual items on the `/saved` page.

---

## 🖱️ Browser Extension (Tampermonkey)

A Tampermonkey userscript adds a save button directly to each tweet on Twitter/X, letting you archive with one click without leaving the page.

**Install:**
1. Install the [Tampermonkey](https://www.tampermonkey.net/) browser extension
2. Start the web UI (`python run_web.py`)
3. Visit `http://localhost:6201/help` and click the install link

**Configure backend URL:**
Click the Tampermonkey icon → find the script → click **⚙️ 设置后端地址** to set your server address (default: `http://localhost:6201`).

The script is located at `tampermonkey/twitter-saver.user.js`.

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
