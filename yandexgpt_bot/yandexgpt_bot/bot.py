"""
Telegram bot powered by YandexGPT 5 Pro with daily rate limiting and security in mind.

Key features
------------
* /ask <question> – get an answer from YandexGPT (15 requests per chat per day by default).
* /image <description> – generate an image from a description using YandexART.
* /setprompt <prompt> – set a custom system prompt for the current chat.
* /reset – clear dialogue history.
* /start – introduction/help.
* /admin – administration panel (only for admins).
* Unlimited usage for chat IDs listed in <code>unlimited_chats.txt</code> (one ID per line).

Security & resiliency
~~~~~~~~~~~~~~~~~~~~~
* Sanitises user input (length ≤ 4000 chars) and escapes assistant replies (no HTML/Markdown parsing).
* Per‑chat history stored in memory only (use Redis/DB for production to avoid DoS).
* SDK calls executed off‑thread to keep the event‑loop responsive.

Requirements
~~~~~~~~~~~~
python‑telegram‑bot >= 22 • yandex‑cloud‑ml‑sdk >= 1 • python‑dotenv (optional)

Environment variables
~~~~~~~~~~~~~~~~~~~~~
  TELEGRAM_BOT_TOKEN – Telegram bot token
  YC_FOLDER_ID        – Yandex Cloud folder ID
  YC_API_KEY          – API key / IAM token
  UNLIMITED_CHAT_IDS_FILE (optional) – path to whitelist file (default: unlimited_chats.txt)

Run:  python yandex_gpt_bot.py
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
import io

from telegram import Update, constants
from telegram.ext import Application, CommandHandler, ContextTypes, Defaults, MessageHandler, filters
from yandex_cloud_ml_sdk import YCloudML
from .config import (
    BOT_TOKEN, YC_FOLDER_ID, YC_API_KEY, DATA_DIR, UNLIMITED_IDS_PATH, STATE_FILE, YANDEXGPT_MODEL, MAX_HISTORY_TURNS, GPT_TEMPERATURE, MAX_QUESTION_LEN, DAILY_LIMIT, IMAGE_GENERATION_LIMIT, DEFAULT_SYSTEM_PROMPT
)
from .handlers import start_cmd, ask_cmd, setprompt_cmd, reset_cmd, image_cmd, error_handler, message_handler

# Import admin panel handlers
from .admin_panel import register_admin_handlers

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# Runtime stores (in-memory)
# ----------------------------------------------------------------------------
ChatContext = List[Dict[str, str]]
PROMPTS: Dict[int, str] = {}
HISTORIES: Dict[int, ChatContext] = {}
DAILY_USAGE: Dict[int, Tuple[_dt.date, int]] = {}
DAILY_IMAGE_USAGE: Dict[int, Tuple[_dt.date, int]] = {}
UNLIMITED_IDS: Set[int] = set()

# ----------------------------------------------------------------------------
# Load whitelist chat IDs
# ----------------------------------------------------------------------------

def _load_unlimited_ids() -> Set[int]:
    # If file does not exist, return empty set
    if not UNLIMITED_IDS_PATH.exists():
        return set()
    ids: Set[int] = set()
    for line in UNLIMITED_IDS_PATH.read_text().splitlines():
        line = line.strip()
        # Try converting to int, handle potential errors and negative numbers
        try:
            ids.add(int(line))
        except ValueError:
            logging.warning(f"Skipping invalid line in unlimited_chats.txt: {line}")
    return ids

UNLIMITED_IDS = _load_unlimited_ids()

# State persistence to JSON
import json
STATE_FILE = Path("state.json")

def _load_state() -> None:
    # Load persisted state if exists
    if not STATE_FILE.exists():
        return
    data = json.loads(STATE_FILE.read_text())
    for k, v in data.get("prompts", {}).items():
        PROMPTS[int(k)] = v
    for k, v in data.get("daily_usage", {}).items():
        d = _dt.date.fromisoformat(v[0])
        DAILY_USAGE[int(k)] = (d, v[1])
    for k, v in data.get("image_usage", {}).items():
        d = _dt.date.fromisoformat(v[0])
        DAILY_IMAGE_USAGE[int(k)] = (d, v[1])


def _save_state() -> None:
    data = {
        "prompts": {str(k): v for k, v in PROMPTS.items()},
        "daily_usage": {str(k): [d.isoformat(), c] for k, (d, c) in DAILY_USAGE.items()},
        "image_usage": {str(k): [d.isoformat(), c] for k, (d, c) in DAILY_IMAGE_USAGE.items()},
        "histories": {str(k): v for k, v in HISTORIES.items()},
    }
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

# load persisted state
_load_state()

# ----------------------------------------------------------------------------
# Yandex Cloud SDK client initialization
# ----------------------------------------------------------------------------
SDK = YCloudML(folder_id=YC_FOLDER_ID, auth=YC_API_KEY)

# ----------------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------------

def _ensure_context(chat_id: int) -> ChatContext:
    if chat_id not in HISTORIES:
        prompt = PROMPTS.get(chat_id, DEFAULT_SYSTEM_PROMPT)
        HISTORIES[chat_id] = [{"role": "system", "text": prompt}]
    return HISTORIES[chat_id]


def _truncate_history(history: ChatContext) -> None:
    extra = len(history) - (1 + 2 * MAX_HISTORY_TURNS)
    if extra > 0:
        del history[1:1 + extra]


def _is_unlimited(chat_id: int) -> bool:
    return chat_id in UNLIMITED_IDS


def _check_and_increment_usage(chat_id: int) -> bool:
    """Return True if under limit (and increment), False if limit exceeded."""
    if _is_unlimited(chat_id):
        return True
    today = _dt.date.today()
    last_date, count = DAILY_USAGE.get(chat_id, (today, 0))
    if last_date != today:
        count = 0  # reset daily counter
    if count >= DAILY_LIMIT:
        return False
    DAILY_USAGE[chat_id] = (today, count + 1)
    return True

def _check_and_increment_image_usage(chat_id: int) -> bool:
    """Return True if under image limit (and increment), False if limit exceeded."""
    if _is_unlimited(chat_id):
        return True
    today = _dt.date.today()
    last_date, count = DAILY_IMAGE_USAGE.get(chat_id, (today, 0))
    if last_date != today:
        count = 0
    if count >= IMAGE_GENERATION_LIMIT:
        return False
    DAILY_IMAGE_USAGE[chat_id] = (today, count + 1)
    return True

async def _generate_reply(history: ChatContext) -> str:
    loop = asyncio.get_event_loop()

    def _call() -> str:
        result = (
            SDK.models.completions(YANDEXGPT_MODEL)
            .configure(temperature=GPT_TEMPERATURE)
            .run(history)
        )
        return result[0].text if result else "(empty response)"

    return await loop.run_in_executor(None, _call)

# ----------------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .defaults(Defaults())
        .build()
    )
    app.add_handler(CommandHandler(["start", "help"], start_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("setprompt", setprompt_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CommandHandler("image", image_cmd))
    
    # Register admin panel handlers
    register_admin_handlers(app)
    
    # Handle regular text messages after commands
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Handle contact sharing events
    app.add_handler(MessageHandler(filters.CONTACT, message_handler))
    
    app.add_error_handler(error_handler)
    logging.info("Bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
