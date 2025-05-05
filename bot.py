"""
Telegram bot powered by YandexGPT 5 Pro with daily rate limiting and security hardening.

Key features
------------
* /ask <question> – get an answer from YandexGPT (15 requests per chat per day by default).
* /setprompt <prompt> – set a custom system prompt for the current chat.
* /reset – clear dialogue history.
* /start – introduction/help.
* Unlimited usage for chat IDs listed in <code>unlimited_chats.txt</code> (one ID per line).

Security & resiliency
~~~~~~~~~~~~~~~~~~~~~
* Sanitises user input (length ≤ 4000 chars) and escapes assistant replies (no HTML/Markdown parsing).
* Per‑chat history stored in memory only (use Redis/DB for production to avoid DoS).
* SDK calls executed off‑thread to keep the event‑loop responsive.

Requirements
~~~~~~~~~~~~
python‑telegram‑bot >= 22 • yandex‑cloud‑ml‑sdk >= 1 • python‑dotenv (optional)

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

from telegram import Update, constants
from telegram.ext import Application, CommandHandler, ContextTypes, Defaults
from yandex_cloud_ml_sdk import YCloudML

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YC_FOLDER_ID = os.getenv("YC_FOLDER_ID")
YC_API_KEY = os.getenv("YC_API_KEY")
UNLIMITED_IDS_PATH = Path(os.getenv("UNLIMITED_CHAT_IDS_FILE", "unlimited_chats.txt"))

if not (BOT_TOKEN and YC_FOLDER_ID and YC_API_KEY):
    raise RuntimeError("Environment variables TELEGRAM_BOT_TOKEN, YC_FOLDER_ID and YC_API_KEY must be set.")

YANDEXGPT_MODEL = "yandexgpt"
MAX_HISTORY_TURNS = 10
GPT_TEMPERATURE = 0.7
MAX_QUESTION_LEN = 4000
DAILY_LIMIT = 15  # per chat

DEFAULT_SYSTEM_PROMPT = "You are YandexGPT 5 Pro, a helpful assistant that answers concisely and accurately."

# ----------------------------------------------------------------------------
# Runtime stores (in‑memory)
# ----------------------------------------------------------------------------
ChatContext = List[Dict[str, str]]
PROMPTS: Dict[int, str] = {}
HISTORIES: Dict[int, ChatContext] = {}
DAILY_USAGE: Dict[int, Tuple[_dt.date, int]] = {}
UNLIMITED_IDS: Set[int] = set()

# ----------------------------------------------------------------------------
# Load unlimited chat IDs
# ----------------------------------------------------------------------------

def _load_unlimited_ids() -> Set[int]:
    if not UNLIMITED_IDS_PATH.exists():
        return set()
    ids: Set[int] = set()
    for line in UNLIMITED_IDS_PATH.read_text().splitlines():
        line = line.strip()
        if line.isdigit():
            ids.add(int(line))
    return ids

UNLIMITED_IDS = _load_unlimited_ids()

# ----------------------------------------------------------------------------
# Yandex Cloud SDK client
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
# Command handlers
# ----------------------------------------------------------------------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = context.bot.username or "the bot"
    text = (
        "👋 <b>Привет!</b> Я помощник на базе <b>YandexGPT 5 Pro</b>.\n\n"
        "<b>Что я умею</b>:\n"
        "• <code>/ask &lt;вопрос&gt;</code> — отвечу (до 15 запросов/день на чат).\n"
        "• <code>/setprompt &lt;текст&gt;</code> — задам системный промпт.\n"
        "• <code>/reset</code> — очищу историю.\n\n"
        "Чаты из whitelist (<code>{path}</code>) не имеют лимитов.\n"
        "В группах используйте <code>/ask@{username}</code>."
    ).format(path=UNLIMITED_IDS_PATH.name, username=username)

    await update.effective_message.reply_text(
        text,
        parse_mode=constants.ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    if not _check_and_increment_usage(chat_id):
        await update.effective_message.reply_text("🚫 Лимит 15 запросов на сегодня исчерпан. Попробуйте завтра.")
        return

    question = " ".join(context.args).strip()
    if not question and update.message.reply_to_message:
        question = update.message.reply_to_message.text or ""

    if not question:
        await update.effective_message.reply_text("Usage: /ask <your question>")
        return

    if len(question) > MAX_QUESTION_LEN:
        await update.effective_message.reply_text("⚠️ Слишком длинный запрос (макс 4000 символов).")
        return

    history = _ensure_context(chat_id)
    history.append({"role": "user", "text": question})
    _truncate_history(history)

    typing_task = context.application.create_task(update.effective_chat.send_chat_action("typing"))

    try:
        answer = await _generate_reply(history)
    except Exception as exc:
        logging.exception("YandexGPT request failed")
        await update.effective_message.reply_text(f"⚠️ Error: {exc}")
        return
    finally:
        typing_task.cancel()

    history.append({"role": "assistant", "text": answer})

    # We do NOT set parse_mode to avoid unintended HTML/Markdown rendering.
    await update.effective_message.reply_text(answer, reply_to_message_id=update.message.message_id, parse_mode=None)


async def setprompt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    new_prompt = " ".join(context.args).strip()
    if not new_prompt:
        await update.effective_message.reply_text("Usage: /setprompt <system prompt text>")
        return

    PROMPTS[chat_id] = new_prompt
    HISTORIES[chat_id] = [{"role": "system", "text": new_prompt}]
    await update.effective_message.reply_text("✅ System prompt updated and context reset.")


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    PROMPTS.pop(chat_id, None)
    HISTORIES.pop(chat_id, None)
    DAILY_USAGE.pop(chat_id, None)
    await update.effective_message.reply_text("🗑️ Context cleared. Using default prompt again.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error("Exception while handling an update:", exc_info=context.error)

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        # Disable global parse_mode to avoid unintended HTML in LLM replies
        .defaults(Defaults())
        .build()
    )

    app.add_handler(CommandHandler(["start", "help"], start_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("setprompt", setprompt_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))

    app.add_error_handler(error_handler)

    logging.info("Bot is starting…")
    app.run_polling()


if __name__ == "__main__":
    main()
