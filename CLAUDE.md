# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Twitter content archival tool (Twitter内容保存工具) written in Python. Saves tweets and media to local storage via browser automation — **no Twitter API credentials required**. Supports CLI and Flask web interface for single tweets and threads.

## Common Commands

```bash
# Web interface (runs on port 6201)
python run_web.py

# CLI
python main.py <twitter_url> [--no-media] [--single-only] [--thread-only] [--output <dir>] [--verbose]

# Tests
python -m pytest tests/
python -m pytest tests/test_twitter_service.py  # single file
python -m pytest tests/ --cov=.

# Setup
pip install -r requirements.txt
python -m playwright install chromium

# Maintenance tools
python tools/clear_all_data.py           # wipe all saved data and DB records
python tools/generate_missing_thumbnails.py  # create video thumbnails via FFmpeg
python tools/regenerate_content.py       # rebuild content.html from metadata
python tools/create_tags_schema.py       # initialize tag DB tables
python tools/batch_generate_tags.py     # bulk-generate tags for all saved tweets
python tools/change_password.py         # change web UI user password
python tools/migrate_to_hierarchical.py # migrate save path structure
```

## Architecture

### Core Components

- **`app.py`** — Flask web application (~2200 lines). Handles all routes, SQLite DB init/migration, background task queue (threading), retry logic, tag generation, and media serving. This is the largest file and central to the web interface.
- **`run_web.py`** — Thin launcher for `app.py` with SSL/port detection.
- **`main.py`** — CLI entry point using `rich` for progress display.
- **`services/playwright_scraper.py`** — **Primary scraper**: Chromium browser automation with anti-detection (random UA, viewport). Handles JS-rendered pages.
- **`services/twitter_service.py`** — Orchestrates scraping, file saving, and media downloads.
- **`services/web_scraper.py`** — **Fallback scraper**: static requests+BeautifulSoup for simple pages.
- **`services/tag_generator.py`** — AI-powered tag generation (rule-based, Gemini API, Claude API). Prompt configured in `prompts.ini`.
- **`services/user_manager.py`** — Login/password system backed by `users.json` (SHA-256 + salt). Default user: `admin`/`admin`.
- **`services/config_manager.py`** — Loads `config.ini` and environment variables; validates config.
- **`services/file_manager.py`** — File I/O, date-based folder structure.
- **`services/media_downloader.py`** — Parallel image/video downloads.
- **`utils/html_to_markdown.py`** — HTML→Markdown conversion and Reader-mode HTML extraction (`convert_html_to_markdown()`, `extract_readable_content()`).
- **`utils/realtime_logger.py`** — In-memory log buffer with SSE streaming to `/api/logs/stream`.

### Key Design Patterns

- **Background queue**: `threading.Thread` processes one task at a time; `queue.Queue` holds pending work. Tasks survive restart via DB `pending` status reload on startup.
- **Retry system**: Failed tasks get exponential backoff (`2^retry_count` minutes, max 60min, default 3 retries). Retry-eligible errors detected by substring match.
- **Share slugs**: Each completed task gets a unique `share_slug` (URL-safe token) for a public view at `/view/<slug>`.
- **Session auth**: Flask sessions backed by a persisted `secret_key.txt`; login required for all UI pages, API endpoints are exempt.
- **Config priority**: env vars → `config.ini` → defaults.

## Database Schema

**File**: `twitter_saver.db`

```sql
-- Core table (auto-migrated with ALTER TABLE for new columns)
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending/processing/completed/failed
    created_at TIMESTAMP, processed_at TIMESTAMP,
    tweet_id TEXT, author_username TEXT, author_name TEXT,
    save_path TEXT, error_message TEXT,
    is_thread BOOLEAN DEFAULT FALSE,
    tweet_count INTEGER DEFAULT 0, media_count INTEGER DEFAULT 0,
    tweet_text TEXT,  -- full-text search
    retry_count INTEGER DEFAULT 0, next_retry_time TIMESTAMP, max_retries INTEGER DEFAULT 3,
    share_slug TEXT UNIQUE,  -- for /view/<slug>
    content_type TEXT DEFAULT 'tweet'
);

-- Tag system (initialized by tools/create_tags_schema.py)
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE, emoji TEXT, color TEXT DEFAULT '#6c757d',
    description TEXT, is_auto_generated BOOLEAN DEFAULT FALSE,
    usage_count INTEGER DEFAULT 0
);
CREATE TABLE tweet_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    confidence REAL DEFAULT 1.0, is_manual BOOLEAN DEFAULT FALSE,
    UNIQUE(task_id, tag_id)
);
CREATE TABLE tag_generation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER, method TEXT, generated_tags TEXT, confidence_scores TEXT
);
```

> **Note**: Tags tables are NOT created by `init_db()` in `app.py`. Run `python tools/create_tags_schema.py` once to initialize them.

## Web Interface Routes

| Route | Purpose |
|---|---|
| `/` | Submit tweet URL |
| `/tasks` | Queue monitor |
| `/saved` | Browse/search saved tweets |
| `/tags` | Tag management UI |
| `/retries` | Failed task retry management |
| `/view/<slug>` | Public tweet viewer by share slug |
| `/debug` | System status, stuck task reset |
| `/media/<task_id>/preview` | First available media (thumbnail→image→video) |
| `/media/<task_id>/<path>` | Serve specific media file |

Key API endpoints: `POST /api/submit`, `GET /api/status/<id>`, `GET /api/tasks`, `GET /api/saved`, `GET /api/tags/all`, `POST /api/tags/generate/<id>`, `GET /api/logs/stream` (SSE).

## Configuration

**`config.ini`** sections:
- `[storage]`: `base_path`, `create_date_folders`
- `[download]`: `max_retries`, `timeout_seconds`
- `[scraper]`: `use_playwright`, `headless`, `debug_mode`

**`prompts.ini`**: Contains the Gemini API prompt template for tag generation (section `[gemini_tag_generation]`, keys `prompt` and `model`).

**Key env vars**: `SAVE_PATH`, `USE_PLAYWRIGHT`, `PLAYWRIGHT_HEADLESS`, `PLAYWRIGHT_DEBUG`, `SSL_CERT_PATH`, `SSL_KEY_PATH`.

## Tag System

Tags are generated automatically after each successful download via `auto_generate_tags_for_tweet()` in `app.py`. Generation methods (in priority order):
1. **Gemini API** — if `gemini_api_key` set in config; uses prompt from `prompts.ini`
2. **Claude API** — if `claude_api_key` set in config
3. **Rule-based** — keyword matching defined in `TagGenerator.keyword_rules`

## Saved Content Structure

```
saved_tweets/YYYY-MM-DD_<tweet_id>/
├── content.txt       # plain text (always present)
├── content.html      # Reader-mode HTML
├── content.md        # Markdown
├── metadata.json     # complete tweet metadata
├── avatar.jpg
├── images/
├── videos/
└── thumbnails/       # video thumbnails (FFmpeg required)
```

## Playwright Debugging

- `PLAYWRIGHT_DEBUG=true` → saves screenshots as `debug_screenshot_<id>_<ts>.png`
- `PLAYWRIGHT_HEADLESS=false` → shows browser window
- Error screenshots: `error_screenshot_<id>_<ts>.png`
