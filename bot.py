"""
Telegram bot powered by YandexGPT 5 Pro.

Key features
------------
* /ask <question> – asynchronously gets an answer from YandexGPT and replies in the chat.
  * Works in private chats and groups (command variants like /ask@YourBotName are supported).
  * Keeps short conversation context per‑chat (system prompt + last N turns).
* /setprompt <prompt text> – sets/updates the system prompt for the current chat.
* /reset – clears the prompt and dialogue history for the current chat.

Requirements
~~~~~~~~~~~~
python-telegram-bot >= 22.0  (PTB v20+ syntax)
yandex-cloud-ml-sdk >= 1.0
python-dotenv (optional) – for loading .env files.

Before running, set the following environment variables (or hard‑code them if you must):
  TELEGRAM_BOT_TOKEN – your Telegram Bot HTTP‑API token
  YC_FOLDER_ID        – Yandex Cloud catalog (folder) id
  YC_API_KEY          – IAM‑token or API key with access to YandexGPT 5 Pro

Run:  python yandex_gpt_bot.py
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List

from telegram import Update, constants
from telegram.ext import (
    Application, CommandHandler, ContextTypes, Defaults,
)

from yandex_cloud_ml_sdk import YCloudML

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YC_FOLDER_ID = os.getenv("YC_FOLDER_ID")
YC_API_KEY = os.getenv("YC_API_KEY")

if not (BOT_TOKEN and YC_FOLDER_ID and YC_API_KEY):
    raise RuntimeError(
        "Environment variables TELEGRAM_BOT_TOKEN, YC_FOLDER_ID and YC_API_KEY "
        "must be set before launching the bot."
    )

# Model name for YandexGPT 5 Pro
YANDEXGPT_MODEL = "yandexgpt"

# Limits
MAX_HISTORY_TURNS = 10  # user/assistant pairs kept in context (plus system prompt)
GPT_TEMPERATURE = 0.7

# Defaults
DEFAULT_SYSTEM_PROMPT = (
    "You are YandexGPT 5 Pro, a helpful assistant that answers concisely and accurately."
)

# ----------------------------------------------------------------------------
# In‑memory chat storage  (use persistent DB/Redis for production)
# ----------------------------------------------------------------------------
ChatContext = List[Dict[str, str]]
PROMPTS: Dict[int, str] = {}
HISTORIES: Dict[int, ChatContext] = {}

# ----------------------------------------------------------------------------
# Yandex Cloud SDK client (shared, thread‑safe)
# ----------------------------------------------------------------------------
SDK = YCloudML(folder_id=YC_FOLDER_ID, auth=YC_API_KEY)

# ----------------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------------

def _ensure_context(chat_id: int) -> ChatContext:
    if chat_id not in HISTORIES:
        system_prompt = PROMPTS.get(chat_id, DEFAULT_SYSTEM_PROMPT)
        HISTORIES[chat_id] = [{"role": "system", "text": system_prompt}]
    return HISTORIES[chat_id]


def _truncate_history(history: ChatContext) -> None:
    excess = len(history) - (1 + 2 * MAX_HISTORY_TURNS)
    if excess > 0:
        del history[1:1 + excess]


async def _generate_reply(history: ChatContext) -> str:
    loop = asyncio.get_event_loop()

    def _call_sdk() -> str:
        result = (
            SDK.models.completions(YANDEXGPT_MODEL)
            .configure(temperature=GPT_TEMPERATURE)
            .run(history)
        )
        return result[0].text if result else "(empty response)"

    return await loop.run_in_executor(None, _call_sdk)


# ----------------------------------------------------------------------------
# Command handlers
# ----------------------------------------------------------------------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = context.bot.username or "the bot"

    text = (
        "👋 <b>Hello!</b> I am an assistant powered by <b>YandexGPT 5 Pro</b>.\n\n"
        "<b>What I can do</b>:\n"
        "• <code>/ask &lt;question&gt;</code> — I will answer your question.\n"
        "• <code>/setprompt &lt;text&gt;</code> — I will set a system prompt for this chat.\n"
        "• <code>/reset</code> — I will clear the history and start fresh.\n\n"
        "Add me to a group and use the command <code>/ask@{username}</code>,\n"
        "so I respond only when needed."
    ).format(username=username)

    await update.effective_message.reply_text(
        text, parse_mode=constants.ParseMode.HTML, disable_web_page_preview=True
    )


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    question = " ".join(context.args).strip()
    if not question and update.message.reply_to_message:
        question = update.message.reply_to_message.text or ""
    if not question:
        await update.effective_message.reply_text("Usage: /ask <your question>")
        return

    history = _ensure_context(chat_id)
    history.append({"role": "user", "text": question})
    _truncate_history(history)

    typing = context.application.create_task(
        update.effective_chat.send_chat_action("typing")
    )
    try:
        answer = await _generate_reply(history)
    except Exception as exc:
        logging.exception("YandexGPT request failed")
        await update.effective_message.reply_text(f"⚠️ Error: {exc}")
        return
    finally:
        typing.cancel()

    history.append({"role": "assistant", "text": answer})

    await update.effective_message.reply_text(
        answer, reply_to_message_id=update.message.message_id
    )


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
    await update.effective_message.reply_text("🗑️ Context cleared. Using default prompt again.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error("Exception while handling an update:", exc_info=context.error)


# ----------------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    app = Application.builder().token(BOT_TOKEN).defaults(Defaults(parse_mode="HTML")).build()

    app.add_handler(CommandHandler(["start", "help"], start_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("setprompt", setprompt_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))

    app.add_error_handler(error_handler)

    logging.info("Bot is starting…")
    app.run_polling()


if __name__ == "__main__":
    main()
