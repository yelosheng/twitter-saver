"""Telegram Bot Service for Twitter Saver

First user to send /start becomes the permanent owner.
Owner can send or forward any message containing a Twitter/X URL to save it.
"""

import asyncio
import json
import logging
import os
import re
import threading
from datetime import datetime
from typing import Optional, Callable

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)

logger = logging.getLogger(__name__)

OWNER_FILE = 'telegram_owner.json'

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_bot_thread: Optional[threading.Thread] = None
_bot_running: bool = False
_bot_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Owner persistence
# ---------------------------------------------------------------------------

def load_owner() -> Optional[dict]:
    if not os.path.exists(OWNER_FILE):
        return None
    try:
        with open(OWNER_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def save_owner(user_id: int, username: str, first_name: str = '') -> None:
    with open(OWNER_FILE, 'w') as f:
        json.dump({
            'user_id': user_id,
            'username': username or first_name or str(user_id),
            'registered_at': datetime.now().isoformat()
        }, f, indent=2)


def clear_owner() -> None:
    if os.path.exists(OWNER_FILE):
        os.remove(OWNER_FILE)


# ---------------------------------------------------------------------------
# Public status API (called by Flask routes)
# ---------------------------------------------------------------------------

def get_status() -> dict:
    return {
        'running': _bot_running,
        'error': _bot_error,
        'owner': load_owner(),
    }


# ---------------------------------------------------------------------------
# URL extraction
# ---------------------------------------------------------------------------

_TWEET_URL_RE = re.compile(
    r'https?://(?:www\.|mobile\.|m\.)?(?:twitter\.com|x\.com)/\w+/status/\d+'
)


def _extract_twitter_url(text: str) -> Optional[str]:
    m = _TWEET_URL_RE.search(text)
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# Handlers (closures over submit_callback)
# ---------------------------------------------------------------------------

def _make_handlers(submit_callback: Callable):

    async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        owner = load_owner()
        if owner is None:
            save_owner(user.id, user.username or '', user.first_name or '')
            await update.message.reply_text(
                f"👋 Hi {user.first_name}! You are now the owner of this bot.\n"
                "Send or forward any tweet link to save it.\n\n"
                "/status — show queue info"
            )
        elif owner['user_id'] == user.id:
            await update.message.reply_text(
                "👋 Welcome back! Send me a Twitter/X URL to save it.\n"
                "/status — show queue info"
            )
        # Non-owner: silently ignore

    async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        owner = load_owner()
        if owner is None or owner['user_id'] != update.effective_user.id:
            return
        # Deferred import — safe since app.py is fully loaded before bot starts
        from app import processing_queue
        queue_size = processing_queue.qsize()
        await update.message.reply_text(
            f"📊 Queue: {queue_size} pending task(s)\n"
            "Full details at the web UI."
        )

    async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        owner = load_owner()
        if owner is None or owner['user_id'] != update.effective_user.id:
            return

        text = (update.message.text or update.message.caption or '').strip()
        url = _extract_twitter_url(text)
        if not url:
            await update.message.reply_text(
                "❌ No Twitter/X URL found. Send a tweet link directly."
            )
            return

        result = submit_callback(url)
        if not result.get('success'):
            await update.message.reply_text("❌ Invalid URL.")
        elif result.get('duplicate'):
            await update.message.reply_text(
                f"⚠️ Already saved (task #{result['task_id']}, status: {result['status']})"
            )
        else:
            await update.message.reply_text(
                f"✅ Added to queue (task #{result['task_id']})"
            )

    return start_handler, status_handler, message_handler


# ---------------------------------------------------------------------------
# Bot runner
# ---------------------------------------------------------------------------

def _run_in_thread(token: str, submit_callback: Callable) -> None:
    global _bot_running, _bot_error
    _bot_running = True
    _bot_error = None
    try:
        start_h, status_h, message_h = _make_handlers(submit_callback)
        application = Application.builder().token(token).build()
        application.add_handler(CommandHandler('start', start_h))
        application.add_handler(CommandHandler('status', status_h))
        application.add_handler(
            MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, message_h)
        )
        # stop_signals=None required when running in a non-main thread
        application.run_polling(stop_signals=None)
    except Exception as e:
        logger.error(f"Telegram bot error: {e}")
        _bot_error = str(e)
    finally:
        _bot_running = False


def start_bot(token: str, submit_callback: Callable) -> None:
    """Start the bot in a daemon thread. No-op if already running."""
    global _bot_thread
    if _bot_running and _bot_thread and _bot_thread.is_alive():
        logger.info("Telegram bot already running, skipping start")
        return
    _bot_thread = threading.Thread(
        target=_run_in_thread,
        args=(token, submit_callback),
        daemon=True,
        name='telegram-bot',
    )
    _bot_thread.start()
    logger.info("Telegram bot thread started")
